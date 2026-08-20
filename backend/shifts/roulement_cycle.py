"""Cycle roulement 6 jours de service + 1 jour de repos."""

from __future__ import annotations

from datetime import date, timedelta

from accounts.models import User
from shifts.models import ShiftAssignment

SERVICE_DAYS = 6
REST_DAYS = 1
CYCLE_LENGTH = SERVICE_DAYS + REST_DAYS


def default_cycle_anchor(day: date | None = None) -> date:
    from django.utils import timezone

    return day or timezone.localdate()


def cycle_position(day: date, anchor: date) -> int:
    """0–5 = jour de service (1–6), 6 = repos."""
    if anchor is None:
        anchor = default_cycle_anchor(day)
    delta = (day - anchor).days
    return delta % CYCLE_LENGTH


def is_rest_day(day: date, anchor: date | None) -> bool:
    if anchor is None:
        return False
    return cycle_position(day, anchor) == SERVICE_DAYS


def is_service_day(day: date, anchor: date | None) -> bool:
    return not is_rest_day(day, anchor)


def cycle_label(day: date, anchor: date | None) -> str:
    if anchor is None:
        return "Cycle non défini"
    pos = cycle_position(day, anchor)
    if pos == SERVICE_DAYS:
        return "Repos"
    return f"Service J{pos + 1}"


def guard_cycle_anchor(guard: User) -> date | None:
    return getattr(guard, "roulement_cycle_anchor", None)


def ensure_guard_cycle_anchor(guard: User, *, save: bool = True) -> date:
    anchor = guard_cycle_anchor(guard)
    if anchor is None:
        anchor = default_cycle_anchor()
        guard.roulement_cycle_anchor = anchor
        if save:
            guard.save(update_fields=["roulement_cycle_anchor"])
    return anchor


def validate_service_days(
    *,
    guard: User,
    shift_date: date,
    roulement_days: int = 1,
) -> None:
    """Refuse une planification qui chevauche un jour de repos."""
    from django.core.exceptions import ValidationError

    anchor = ensure_guard_cycle_anchor(guard, save=True)
    days = max(1, min(int(roulement_days or 1), 31))
    rest_days: list[date] = []
    for offset in range(days):
        day = shift_date + timedelta(days=offset)
        if is_rest_day(day, anchor):
            rest_days.append(day)
    if rest_days:
        labels = ", ".join(d.strftime("%d/%m/%Y") for d in rest_days)
        raise ValidationError(
            f"{guard.username} est en repos le {labels} (cycle 6j service + 1j repos). "
            "Choisissez une autre date ou ajustez l'ancrage du cycle."
        )


def assignments_by_date(
    guard: User,
    *,
    start: date,
    end: date,
) -> dict[date, list[ShiftAssignment]]:
    rows = (
        ShiftAssignment.objects.filter(
            guard=guard,
            shift_date__gte=start,
            shift_date__lte=end,
            status=ShiftAssignment.Status.ROULEMENT,
        )
        .select_related("site")
        .order_by("shift_date", "start_time")
    )
    grouped: dict[date, list[ShiftAssignment]] = {}
    for row in rows:
        grouped.setdefault(row.shift_date, []).append(row)
    return grouped


def build_guard_calendar(
    guard: User,
    *,
    start: date,
    days: int = 14,
    today: date | None = None,
) -> list[dict]:
    """Calendrier jour par jour pour un RLT (repos, mission, service libre)."""
    from django.utils import timezone

    today = today or timezone.localdate()
    anchor = guard_cycle_anchor(guard)
    end = start + timedelta(days=days - 1)
    by_date = assignments_by_date(guard, start=start, end=end)
    out: list[dict] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        missions = by_date.get(day, [])
        rest = is_rest_day(day, anchor) if anchor else False
        if rest:
            status = "rest"
            status_label = "Repos"
        elif missions:
            status = "mission"
            status_label = "Mission"
        elif anchor:
            status = "free"
            status_label = "Service (libre)"
        else:
            status = "unknown"
            status_label = "—"
        out.append(
            {
                "date": day,
                "cycle_label": cycle_label(day, anchor),
                "status": status,
                "status_label": status_label,
                "missions": missions,
                "is_today": day == today,
            }
        )
    return out


def build_team_calendars(
    guards,
    *,
    start: date,
    days: int = 14,
) -> list[dict]:
    """Calendriers pour la liste d'équipe roulement."""
    return [
        {
            "guard": guard,
            "anchor": guard_cycle_anchor(guard),
            "today_label": cycle_label(start, guard_cycle_anchor(guard)),
            "is_rest_today": is_rest_day(start, guard_cycle_anchor(guard)),
            "days": build_guard_calendar(guard, start=start, days=days),
        }
        for guard in guards
    ]
