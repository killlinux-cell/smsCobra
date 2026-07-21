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

_RETARD_PREFIX = "Retard prise de service"

PRESENCE_DECISION_PRESENT = "present"
PRESENCE_DECISION_ABSENT = "absent"


def normalize_presence_decision(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in ("absent", "absence", "confirm_absent", "confirmed_absent"):
        return PRESENCE_DECISION_ABSENT
    return PRESENCE_DECISION_PRESENT


def presence_decision_label(decision: str) -> str:
    if decision == PRESENCE_DECISION_ABSENT:
        return "absence confirmée"
    return "présence justifiée"


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


def assignment_has_supervisor_decision(assignment) -> bool:
    """
    True si un superviseur a déjà tranché Présent/Absent pour ce créneau.
    Survit au remplacement d'affectation (site + vigile + date).
    """
    from alerts.models import LateAlert
    from django.db.models import Q

    q = Q()
    for prefix in _GUARD_ALERT_PREFIXES:
        q |= Q(message__startswith=prefix)

    if LateAlert.objects.filter(
        assignment__site_id=assignment.site_id,
        assignment__guard_id=assignment.guard_id,
        assignment__shift_date=assignment.shift_date,
        status=LateAlert.Status.ACKNOWLEDGED,
    ).filter(q).exists():
        return True

    report = AttendanceReport.objects.filter(
        site_id=assignment.site_id,
        guard_id=assignment.guard_id,
        report_date=assignment.shift_date,
    ).first()
    if not report:
        return False
    if report.was_absent:
        return True
    notes = (report.notes or "").lower()
    return "acquittée" in notes or "acquittee" in notes


def mark_justified_presence_from_alert(alert) -> None:
    """
    Présence justifiée : compte comme présent au calendrier
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


def mark_confirmed_absence_from_alert(alert) -> None:
    """Absence confirmée par le superviseur à l'acquittement."""
    assignment = alert.assignment
    if not assignment or not _is_guard_presence_alert(alert.message):
        return

    has_start = Checkin.objects.filter(
        assignment=assignment,
        type=Checkin.Type.START,
    ).exists()

    report, _ = AttendanceReport.objects.get_or_create(
        site_id=assignment.site_id,
        guard_id=assignment.guard_id,
        report_date=assignment.shift_date,
    )
    update_fields: list[str] = []

    if not has_start:
        if report.started_at is not None:
            report.started_at = None
            update_fields.append("started_at")
        if report.ended_at is not None:
            report.ended_at = None
            update_fields.append("ended_at")
        ShiftAssignment.objects.filter(pk=assignment.pk).update(
            status=ShiftAssignment.Status.MISSED
        )

    if not report.was_absent:
        report.was_absent = True
        update_fields.append("was_absent")

    if update_fields:
        report.save(update_fields=update_fields)


def apply_presence_decision_from_alert(alert, *, presence_decision: str) -> None:
    decision = normalize_presence_decision(presence_decision)
    if decision == PRESENCE_DECISION_ABSENT:
        mark_confirmed_absence_from_alert(alert)
    else:
        mark_justified_presence_from_alert(alert)


def log_alert_acknowledged_to_report(
    alert,
    admin_user,
    *,
    presence_decision: str = PRESENCE_DECISION_PRESENT,
) -> None:
    """Ajoute une ligne dans AttendanceReport.notes (synthèse + export CSV)."""
    assignment = alert.assignment
    if not assignment or not admin_user or not admin_user.pk:
        return

    decision = normalize_presence_decision(presence_decision)
    apply_presence_decision_from_alert(alert, presence_decision=decision)

    admin_name = (admin_user.get_full_name() or "").strip() or admin_user.username
    ts = alert.acknowledged_at or timezone.now()
    ts_str = timezone.localtime(ts).strftime("%d/%m/%Y %H:%M")
    kind = alert_kind_label(alert.message)
    msg = (alert.message or "").strip()[:240]
    decision_txt = presence_decision_label(decision)

    line = (
        f"[{ts_str}] Alerte n°{alert.id} acquittée par {admin_name} ({kind}) "
        f"— {decision_txt}"
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


def acknowledge_late_alert(
    alert,
    admin_user,
    *,
    presence_decision: str = PRESENCE_DECISION_PRESENT,
):
    """Passe une alerte en acquittée et trace dans les rapports."""
    from alerts.models import LateAlert

    alert.status = LateAlert.Status.ACKNOWLEDGED
    alert.acknowledged_at = timezone.now()
    alert.admin_recipient = admin_user
    alert.save(update_fields=["status", "acknowledged_at", "admin_recipient"])
    log_alert_acknowledged_to_report(
        alert,
        admin_user,
        presence_decision=presence_decision,
    )
    from webadmin.alert_state import invalidate_alert_summary_cache

    if alert.assignment_id:
        invalidate_alert_summary_cache(alert.assignment.shift_date)
    return alert


def acknowledge_assignment_late(
    assignment: ShiftAssignment,
    admin_user,
    *,
    presence_decision: str = PRESENCE_DECISION_PRESENT,
):
    """
    Acquitte le retard d'une affectation depuis « Remplacement à prévoir » :
    alerte ouverte existante, sinon création à la volée (scan Celery pas encore passé).
    """
    from alerts.models import LateAlert

    alert = (
        LateAlert.objects.filter(
            assignment=assignment,
            status=LateAlert.Status.OPEN,
        )
        .order_by("-triggered_at")
        .first()
    )
    if alert is None:
        alert = (
            LateAlert.objects.filter(
                assignment=assignment,
                status=LateAlert.Status.ACKNOWLEDGED,
                message__startswith=_RETARD_PREFIX,
            )
            .order_by("-triggered_at")
            .first()
        )
        if alert:
            apply_presence_decision_from_alert(
                alert,
                presence_decision=presence_decision,
            )
            return alert

    if alert is None:
        guard = assignment.guard
        site = assignment.site
        msg = f"{_RETARD_PREFIX} : {guard.username} sur {site.name}"
        alert = LateAlert.objects.create(assignment=assignment, message=msg[:300])

    return acknowledge_late_alert(
        alert,
        admin_user,
        presence_decision=presence_decision,
    )
