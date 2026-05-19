"""Fenêtres horaires des pointages début / fin de service."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

# Délai max après la fin prévue du créneau pour accepter un pointage de fin.
END_GRACE_AFTER_MINUTES = 120


def site_tz(site):
    tz_name = (getattr(site, "timezone", None) or "").strip()
    if not tz_name:
        return timezone.get_current_timezone()
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.get_current_timezone()


def assignment_window(assignment):
    """Fenêtre réelle du créneau (gère les postes de nuit qui finissent le lendemain)."""
    tz = site_tz(assignment.site)
    start_at = datetime.combine(assignment.shift_date, assignment.start_time, tzinfo=tz)
    end_day = assignment.shift_date
    if assignment.end_time <= assignment.start_time:
        end_day = assignment.shift_date + timedelta(days=1)
    end_at = datetime.combine(end_day, assignment.end_time, tzinfo=tz)
    return start_at, end_at, tz


def _now_local(assignment, now=None):
    _, _, site_tzinfo = assignment_window(assignment)
    ts = now if now is not None else timezone.now()
    return ts.astimezone(site_tzinfo)


def validate_start_window(assignment, now=None) -> tuple[bool, str | None]:
    start_at, end_at, _ = assignment_window(assignment)
    now_local = _now_local(assignment, now)
    if now_local < start_at or now_local > end_at:
        return False, (
            "Prise de service hors créneau autorisé pour cette affectation "
            f"({start_at.strftime('%d/%m/%Y %H:%M')} - {end_at.strftime('%d/%m/%Y %H:%M')})."
        )
    return True, None


def validate_end_window(assignment, now=None) -> tuple[bool, str | None]:
    start_at, end_at, _ = assignment_window(assignment)
    now_local = _now_local(assignment, now)
    if now_local < start_at:
        return False, (
            "Fin de service hors créneau autorisé pour cette affectation "
            f"({start_at.strftime('%d/%m/%Y %H:%M')} - {end_at.strftime('%d/%m/%Y %H:%M')})."
        )
    if now_local < end_at:
        return False, (
            "Fin de service trop tôt. Fin prévue à "
            f"{end_at.strftime('%d/%m/%Y %H:%M')}."
        )
    latest = end_at + timedelta(minutes=END_GRACE_AFTER_MINUTES)
    if now_local > latest:
        return False, (
            "Fin de service hors créneau autorisé pour cette affectation "
            f"({start_at.strftime('%d/%m/%Y %H:%M')} - {end_at.strftime('%d/%m/%Y %H:%M')})."
        )
    return True, None
