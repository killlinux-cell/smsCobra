"""Clôture superviseur d'une affectation (fin de service sans l'app vigile)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from alerts.models import LateAlert
from alerts.services import resolve_fin_sans_pointage_alerts
from checkins.models import Checkin
from reports.attendance import is_early_end
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment


class ForceEndError(Exception):
    pass


@transaction.atomic
def supervisor_force_end_assignment(
    assignment: ShiftAssignment,
    *,
    actor,
    reason: str = "",
) -> Checkin:
    """
    Enregistre une fin de service côté superviseur.
    Contourne la relève non pointée et la fenêtre horaire mobile.
    """
    assignment = (
        ShiftAssignment.objects.select_for_update()
        .select_related("site", "guard")
        .get(pk=assignment.pk)
    )

    if not Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists():
        raise ForceEndError("Aucune prise de service sur cette affectation.")
    if Checkin.objects.filter(assignment=assignment, type=Checkin.Type.END).exists():
        raise ForceEndError("La fin de service est déjà enregistrée.")

    site = assignment.site
    last_start = (
        Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START)
        .order_by("-timestamp")
        .first()
    )
    if last_start and last_start.latitude is not None:
        lat, lon = last_start.latitude, last_start.longitude
        within = last_start.within_geofence
        distance = last_start.distance_from_site_meters
    else:
        lat = site.latitude if site.latitude is not None else 0
        lon = site.longitude if site.longitude is not None else 0
        within = True
        distance = None

    end = Checkin.objects.create(
        assignment=assignment,
        guard=assignment.guard,
        type=Checkin.Type.END,
        latitude=lat,
        longitude=lon,
        within_geofence=within,
        distance_from_site_meters=distance,
        biometric_reason="supervisor_dashboard",
    )

    report, _ = AttendanceReport.objects.get_or_create(
        site=site,
        guard=assignment.guard,
        report_date=assignment.shift_date,
    )
    report.ended_at = end.timestamp
    report.was_absent = is_early_end(end.timestamp, assignment)
    _append_supervisor_note(
        report,
        assignment=assignment,
        actor=actor,
        reason=reason,
        ended_at=end.timestamp,
    )
    report.save(update_fields=["ended_at", "was_absent", "notes"])

    if assignment.status in ShiftAssignment.active_on_duty_statuses():
        ShiftAssignment.objects.filter(pk=assignment.pk).update(
            status=ShiftAssignment.Status.COMPLETED
        )

    LateAlert.objects.filter(
        assignment=assignment,
        status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
        message__startswith="Presence:",
    ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())

    resolve_fin_sans_pointage_alerts(assignment)
    return end


def _append_supervisor_note(
    report: AttendanceReport,
    *,
    assignment: ShiftAssignment,
    actor,
    reason: str,
    ended_at,
) -> None:
    admin_name = (actor.get_full_name() or "").strip() if actor else ""
    if not admin_name and actor:
        admin_name = actor.username
    ts_str = timezone.localtime(ended_at).strftime("%d/%m/%Y %H:%M")
    line = (
        f"[{ts_str}] Fin de service validée par {admin_name} (dashboard) "
        f"pour affectation n°{assignment.id}"
    )
    cleaned = (reason or "").strip()
    if cleaned:
        line = f"{line} — {cleaned[:240]}"
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line
