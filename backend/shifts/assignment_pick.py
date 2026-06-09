"""Sélection de l'affectation active pour un vigile (aligné sur l'app mobile)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from shifts.models import ShiftAssignment


def _same_calendar_date(a: date, b: date) -> bool:
    return a.year == b.year and a.month == b.month and a.day == b.day


def _minutes_from_time(t: time) -> int:
    return t.hour * 60 + t.minute


def assignment_is_active_now(assignment: ShiftAssignment, now: datetime) -> bool:
    local = timezone.localtime(now)
    today = local.date()
    yesterday = today - timedelta(days=1)
    now_min = local.hour * 60 + local.minute
    start_min = _minutes_from_time(assignment.start_time)
    end_min = _minutes_from_time(assignment.end_time)
    crosses_midnight = start_min > end_min

    if not crosses_midnight:
        if not _same_calendar_date(assignment.shift_date, today):
            return False
        return start_min <= now_min < end_min
    if _same_calendar_date(assignment.shift_date, today) and now_min >= start_min:
        return True
    if _same_calendar_date(assignment.shift_date, yesterday) and now_min < end_min:
        return True
    return False


def pick_active_assignment(
    assignments: list[ShiftAssignment],
    *,
    now: datetime | None = None,
) -> ShiftAssignment | None:
    if not assignments:
        return None
    now = now or timezone.now()
    for row in assignments:
        if assignment_is_active_now(row, now):
            return row
    today = timezone.localdate()
    for row in assignments:
        if row.shift_date == today:
            return row
    return assignments[0]


def assignments_for_guard(
    guard_id: int,
    *,
    site_id: int | None = None,
    now: datetime | None = None,
) -> list[ShiftAssignment]:
    now = now or timezone.now()
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    qs = ShiftAssignment.objects.select_related("site", "guard").filter(
        guard_id=guard_id,
        shift_date__in=[yesterday, today],
        status__in=ShiftAssignment.active_on_duty_statuses(),
    )
    if site_id is not None:
        qs = qs.filter(site_id=site_id)
    return list(qs.order_by("shift_date", "start_time"))


def pick_assignment_for_guard(
    guard_id: int,
    *,
    site_id: int | None = None,
    now: datetime | None = None,
) -> ShiftAssignment | None:
    return pick_active_assignment(
        assignments_for_guard(guard_id, site_id=site_id, now=now),
        now=now,
    )
