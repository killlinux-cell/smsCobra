"""Règles métier : retard à la prise de service (tolérance + fuseau du site)."""

from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_tz
from django.utils.dateparse import parse_time

from shifts.models import ShiftAssignment


def is_start_late(checkin_timestamp, assignment: ShiftAssignment) -> bool:
    """
    Retard si la prise de service est strictement après
    (heure prévue du créneau + late_tolerance_minutes du site),
    comparé dans le fuseau horaire du site.

    Ancienne logique (timestamp.time() > start_time) ignorait la tolérance et
    marquait « retard » dès la moindre seconde après l'heure prévue.
    """
    site = assignment.site
    try:
        tz = ZoneInfo(site.timezone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    st = assignment.start_time
    if isinstance(st, str):
        st = parse_time(st) or time(0, 0)

    start_local = datetime.combine(assignment.shift_date, st, tzinfo=tz)
    deadline = start_local + timedelta(minutes=int(site.late_tolerance_minutes))

    ts = checkin_timestamp
    if dj_tz.is_naive(ts):
        ts = dj_tz.make_aware(ts, tz)
    at_site = ts.astimezone(tz)
    return at_site > deadline
