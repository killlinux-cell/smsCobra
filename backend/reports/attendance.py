"""Présence / absence journalière (fin anticipée, fin non pointée, pas de prise de service)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from checkins.models import Checkin
from checkins.window import assignment_window
from shifts.models import ShiftAssignment

from .models import AttendanceReport


def is_early_end(end_timestamp, assignment: ShiftAssignment) -> bool:
    """True si la fin de service est enregistrée avant l'heure de fin prévue du créneau."""
    _, end_at, tz = assignment_window(assignment)
    ts = end_timestamp
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts, tz)
    return ts.astimezone(tz) < end_at


def _shift_is_over(assignment: ShiftAssignment, now) -> bool:
    _, end_at, tz = assignment_window(assignment)
    now_local = now.astimezone(tz)
    grace = timedelta(minutes=int(assignment.site.late_tolerance_minutes))
    return now_local > end_at + grace


def compute_was_absent(assignment: ShiftAssignment, *, now=None) -> bool:
    """
    Absent pour la journée si :
    - créneau terminé sans prise de service ;
    - prise de service sans fin pointée après la fin du créneau ;
    - fin pointée avant l'heure prévue.
    """
    now = now if now is not None else timezone.now()
    has_start = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists()
    end_checkin = (
        Checkin.objects.filter(assignment=assignment, type=Checkin.Type.END)
        .order_by("timestamp")
        .first()
    )
    shift_over = _shift_is_over(assignment, now)

    if not has_start:
        return shift_over
    if end_checkin is None:
        return shift_over
    return is_early_end(end_checkin.timestamp, assignment)


def refresh_attendance_report(assignment: ShiftAssignment, *, now=None) -> AttendanceReport:
    """Met à jour le rapport journalier à partir des pointages de l'affectation."""
    report, _ = AttendanceReport.objects.get_or_create(
        site=assignment.site,
        guard=assignment.guard,
        report_date=assignment.shift_date,
    )
    absent = compute_was_absent(assignment, now=now)
    if report.was_absent != absent:
        report.was_absent = absent
        report.save(update_fields=["was_absent"])
    return report
