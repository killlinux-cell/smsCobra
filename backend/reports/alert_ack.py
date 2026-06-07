"""Trace écrite des acquittements d'alertes dans les rapports de pointage."""

from __future__ import annotations

from django.utils import timezone

from checkins.models import Checkin
from checkins.window import assignment_window
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment

_GUARD_ALERT_PREFIXES = (
    "Retard prise de service",
    "Passation:",
    "Absence:",
    "FinSansPointage:",
)


def alert_kind_label(message: str) -> str:
    m = (message or "").strip()
    if m.startswith("Retard prise de service"):
        return "Retard prise de service"
    if m.startswith("Passation:"):
        return "Passation / relève"
    if m.startswith("Absence:"):
        return "Absence"
    if m.startswith("FinSansPointage:"):
        return "Fin non pointée"
    if m.startswith("Presence:"):
        return "Présence"
    return "Alerte"


def _is_guard_presence_alert(message: str) -> bool:
    m = (message or "").strip()
    return any(m.startswith(prefix) for prefix in _GUARD_ALERT_PREFIXES)


def mark_justified_presence_from_alert(alert) -> None:
    """
    Acquittement = absence justifiée : compte comme présent au calendrier
    (was_absent=False + horaires du créneau si aucun pointage réel).
    """
    assignment = alert.assignment
    if not assignment or not _is_guard_presence_alert(alert.message):
        return

    start_at, end_at, _ = assignment_window(assignment)
    report, _ = AttendanceReport.objects.get_or_create(
        site_id=assignment.site_id,
        guard_id=assignment.guard_id,
        report_date=assignment.shift_date,
    )
    update_fields: list[str] = []
    if report.was_absent:
        report.was_absent = False
        update_fields.append("was_absent")
    if report.started_at is None:
        report.started_at = start_at
        update_fields.append("started_at")
    if report.ended_at is None:
        report.ended_at = end_at
        update_fields.append("ended_at")
    if update_fields:
        report.save(update_fields=update_fields)

    if assignment.status == ShiftAssignment.Status.MISSED:
        has_start = Checkin.objects.filter(
            assignment=assignment,
            type=Checkin.Type.START,
        ).exists()
        if not has_start:
            ShiftAssignment.objects.filter(pk=assignment.pk).update(
                status=ShiftAssignment.Status.SCHEDULED
            )


def log_alert_acknowledged_to_report(alert, admin_user) -> None:
    """Ajoute une ligne dans AttendanceReport.notes (synthèse + export CSV)."""
    assignment = alert.assignment
    if not assignment or not admin_user or not admin_user.pk:
        return

    mark_justified_presence_from_alert(alert)

    admin_name = (admin_user.get_full_name() or "").strip() or admin_user.username
    ts = alert.acknowledged_at or timezone.now()
    ts_str = timezone.localtime(ts).strftime("%d/%m/%Y %H:%M")
    kind = alert_kind_label(alert.message)
    msg = (alert.message or "").strip()[:240]

    line = (
        f"[{ts_str}] Alerte n°{alert.id} acquittée par {admin_name} ({kind})"
        f"{f' : {msg}' if msg else ''}"
    )

    report, _ = AttendanceReport.objects.get_or_create(
        site_id=assignment.site_id,
        guard_id=assignment.guard_id,
        report_date=assignment.shift_date,
    )
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line
    report.save(update_fields=["notes"])
