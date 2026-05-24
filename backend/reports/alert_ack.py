"""Trace écrite des acquittements d'alertes dans les rapports de pointage."""

from __future__ import annotations

from django.utils import timezone

from reports.models import AttendanceReport


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


def log_alert_acknowledged_to_report(alert, admin_user) -> None:
    """Ajoute une ligne dans AttendanceReport.notes (synthèse + export CSV)."""
    assignment = alert.assignment
    if not assignment or not admin_user or not admin_user.pk:
        return

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
