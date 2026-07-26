"""Correction manuelle rétroactive des présences / absences (admin société)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from checkins.models import Checkin
from checkins.window import assignment_window
from reports.alert_ack import (
    PRESENCE_DECISION_ABSENT,
    normalize_presence_decision,
    presence_decision_label,
)
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment

MANUAL_CORRECTION_MARKER = "Correction manuelle"


def report_presence_locked_by_supervisor(report: AttendanceReport) -> bool:
    """True si une décision superviseur ou admin ne doit plus être écrasée par le calcul auto."""
    notes = (report.notes or "").lower()
    return any(
        marker in notes
        for marker in ("acquittée", "acquittee", MANUAL_CORRECTION_MARKER.lower())
    )


def _assignments_for_report(report: AttendanceReport):
    return ShiftAssignment.objects.filter(
        site_id=report.site_id,
        guard_id=report.guard_id,
        shift_date=report.report_date,
    ).exclude(status=ShiftAssignment.Status.EXTRA)


def _append_audit_note(report: AttendanceReport, *, actor, decision: str, reason: str) -> None:
    admin_name = (actor.get_full_name() or "").strip() or actor.username
    ts_str = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    decision_txt = presence_decision_label(decision)
    line = (
        f"[{ts_str}] {MANUAL_CORRECTION_MARKER} par {admin_name} "
        f"— {decision_txt} — {reason.strip()[:400]}"
    )
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line


def admin_adjust_attendance_report(
    report: AttendanceReport,
    *,
    presence_decision: str,
    actor,
    reason: str,
) -> AttendanceReport:
    """
    Corrige rétroactivement la présence ou l'absence d'un vigile pour un jour passé.
    Ne modifie pas les pointages réels (Checkin) déjà enregistrés.
    """
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Le motif de correction est obligatoire.")
    if not actor or not getattr(actor, "pk", None):
        raise ValidationError("Utilisateur administrateur requis.")

    decision = normalize_presence_decision(presence_decision)
    assignments = list(_assignments_for_report(report))
    update_fields: list[str] = []

    if decision == PRESENCE_DECISION_ABSENT:
        has_any_start = False
        for assignment in assignments:
            has_start = Checkin.objects.filter(
                assignment=assignment,
                type=Checkin.Type.START,
            ).exists()
            if has_start:
                has_any_start = True
            elif assignment.status != ShiftAssignment.Status.MISSED:
                ShiftAssignment.objects.filter(pk=assignment.pk).update(
                    status=ShiftAssignment.Status.MISSED
                )
        if report.was_absent is not True:
            report.was_absent = True
            update_fields.append("was_absent")
        if not has_any_start:
            if report.started_at is not None:
                report.started_at = None
                update_fields.append("started_at")
            if report.ended_at is not None:
                report.ended_at = None
                update_fields.append("ended_at")
    else:
        if report.was_absent is not False:
            report.was_absent = False
            update_fields.append("was_absent")
        if report.started_at is None and assignments:
            start_at, end_at, _ = assignment_window(assignments[0])
            report.started_at = start_at
            report.ended_at = end_at
            update_fields.extend(["started_at", "ended_at"])
        for assignment in assignments:
            has_start = Checkin.objects.filter(
                assignment=assignment,
                type=Checkin.Type.START,
            ).exists()
            if not has_start and assignment.status == ShiftAssignment.Status.MISSED:
                ShiftAssignment.objects.filter(pk=assignment.pk).update(
                    status=ShiftAssignment.Status.SCHEDULED
                )

    _append_audit_note(report, actor=actor, decision=decision, reason=reason)
    if "notes" not in update_fields:
        update_fields.append("notes")
    if update_fields:
        report.save(update_fields=list(dict.fromkeys(update_fields)))
    return report
