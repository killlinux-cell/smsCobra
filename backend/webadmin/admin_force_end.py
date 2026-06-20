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
    source_label: str = "dashboard",
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
        biometric_reason="supervisor_force_end",
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
        source_label=source_label,
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


def stale_open_assignments(*, today=None, site_id: int | None = None):
    """Affectations avec START sans END et date de poste strictement avant aujourd'hui."""
    from webadmin.open_shifts import _open_assignments_queryset

    day = today or timezone.localdate()
    return _open_assignments_queryset(stale_only=True, today=day, site_id=site_id)


def bulk_force_end_stale_open_shifts(
    *,
    actor,
    reason: str,
    site_id: int | None = None,
    today=None,
    apply: bool = False,
) -> dict:
    """
    Clôture en masse les postes ouverts datés avant [today].
    Retourne {candidates, applied, errors}.
    """
    qs = stale_open_assignments(today=today, site_id=site_id)
    candidates = list(qs)
    result = {"candidates": candidates, "applied": 0, "errors": []}
    if not apply:
        return result

    for assignment in candidates:
        try:
            supervisor_force_end_assignment(
                assignment,
                actor=actor,
                reason=reason,
                source_label="alignement bulk",
            )
            result["applied"] += 1
        except ForceEndError as exc:
            result["errors"].append((assignment.pk, str(exc)))
    return result


def _append_supervisor_note(
    report: AttendanceReport,
    *,
    assignment: ShiftAssignment,
    actor,
    reason: str,
    ended_at,
    source_label: str = "dashboard",
) -> None:
    admin_name = (actor.get_full_name() or "").strip() if actor else ""
    if not admin_name and actor:
        admin_name = actor.username
    if not admin_name:
        admin_name = "Système"
    ts_str = timezone.localtime(ended_at).strftime("%d/%m/%Y %H:%M")
    line = (
        f"[{ts_str}] Fin de service validée par {admin_name} ({source_label}) "
        f"pour affectation n°{assignment.id}"
    )
    cleaned = (reason or "").strip()
    if cleaned:
        line = f"{line} — {cleaned[:240]}"
    existing = (report.notes or "").strip()
    if line in existing:
        return
    report.notes = f"{existing}\n{line}".strip() if existing else line
