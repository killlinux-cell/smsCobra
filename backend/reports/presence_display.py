"""Libellés de présence affichés dans le dashboard (≠ simple was_absent)."""

from __future__ import annotations

from django.utils import timezone

from reports.models import AttendanceReport


def report_presence_badge(report: AttendanceReport) -> dict:
    """
    Statut lisible pour les superviseurs.

    « Présent » uniquement si début + fin enregistrés et journée non absente.
    Prise seule ≠ journée terminée ni « présent » au sens paie.
    """
    today = timezone.localdate()

    if report.was_absent:
        return {"label": "Absent", "css": "bg-danger", "code": "absent"}

    if not report.started_at:
        return {"label": "Non pointé", "css": "bg-secondary", "code": "none"}

    if not report.ended_at:
        if report.report_date < today:
            return {
                "label": "Fin non pointée",
                "css": "bg-warning text-dark",
                "code": "incomplete",
            }
        return {"label": "En service", "css": "bg-info text-dark", "code": "in_service"}

    if report.was_late:
        return {"label": "Présent (retard)", "css": "bg-warning text-dark", "code": "present_late"}

    return {"label": "Présent", "css": "bg-success", "code": "present"}
