from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

from checkins.models import Checkin
from shifts.models import ShiftAssignment
from shifts.services import ensure_assignments_for_dates

from .models import LateAlert
from .services import send_push_to_admins


def _aware_at(site, day, t, plus_minutes: int = 0):
    tz = ZoneInfo(site.timezone or "UTC")
    local = datetime.combine(day, t, tzinfo=tz) + timedelta(minutes=plus_minutes)
    return local


@shared_task
def detect_missed_shift_task():
    now = timezone.now()
    today = date.today()
    ensure_assignments_for_dates([today, today + timedelta(days=1)])

    assignments = ShiftAssignment.objects.select_related("site", "guard").filter(
        shift_date=today,
        status__in=[ShiftAssignment.Status.SCHEDULED, ShiftAssignment.Status.REPLACED],
    )
    for assignment in assignments:
        deadline = _aware_at(
            assignment.site,
            assignment.shift_date,
            assignment.start_time,
            assignment.site.late_tolerance_minutes,
        )
        has_start = Checkin.objects.filter(
            assignment=assignment,
            type=Checkin.Type.START,
        ).exists()
        alert_exists = LateAlert.objects.filter(
            assignment=assignment,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="Retard prise de service :",
        ).exists()
        if now > deadline and not has_start and not alert_exists:
            alert = LateAlert.objects.create(
                assignment=assignment,
                message=(
                    f"Retard prise de service : {assignment.guard.username} sur {assignment.site.name}"
                ),
            )
            send_push_to_admins(
                "Alerte retard SMS",
                alert.message,
                {"alert_id": str(alert.id), "site": assignment.site.name},
            )

    incoming_qs = (
        ShiftAssignment.objects.filter(
            shift_date=today,
            status=ShiftAssignment.Status.SCHEDULED,
            outgoing_handover_assignments__isnull=False,
        )
        .select_related("site", "guard")
        .distinct()
    )
    for incoming in incoming_qs:
        grace = incoming.site.relief_late_alert_minutes
        deadline = _aware_at(incoming.site, incoming.shift_date, incoming.start_time, grace)
        has_start = Checkin.objects.filter(
            assignment=incoming,
            type=Checkin.Type.START,
        ).exists()
        alert_exists = LateAlert.objects.filter(
            assignment=incoming,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="Passation:",
        ).exists()
        if now > deadline and not has_start and not alert_exists:
            outgoing = incoming.outgoing_handover_assignments.first()
            msg = (
                f"Passation: le releve {incoming.guard.username} n'a pas pris son service sur "
                f"{incoming.site.name} (prevu {incoming.start_time.strftime('%H:%M')}, "
                f"depasse de plus de {grace} min). Vigile en poste : {outgoing.guard.username if outgoing else 'N/A'}."
            )
            alert = LateAlert.objects.create(assignment=incoming, message=msg[:300])
            send_push_to_admins(
                "Alerte passation SMS",
                alert.message,
                {"alert_id": str(alert.id), "site": incoming.site.name, "type": "passation"},
            )

    # Fin de service non pointée : prise enregistrée, pas de fin, après fin prévue + tolérance.
    for assignment in (
        ShiftAssignment.objects.filter(
            shift_date=today,
            status__in=[ShiftAssignment.Status.SCHEDULED, ShiftAssignment.Status.REPLACED],
        )
        .select_related("site", "guard")
        .iterator()
    ):
        has_start = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists()
        has_end = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.END).exists()
        if not has_start or has_end:
            continue
        deadline = _aware_at(
            assignment.site,
            assignment.shift_date,
            assignment.end_time,
            assignment.site.late_tolerance_minutes,
        )
        if now <= deadline:
            continue
        fin_alert_exists = LateAlert.objects.filter(
            assignment=assignment,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="FinSansPointage:",
        ).exists()
        if fin_alert_exists:
            continue
        msg = (
            f"FinSansPointage: fin non pointée — {assignment.guard.display_name} @ {assignment.site.name} "
            f"(fin prévue {assignment.end_time.strftime('%H:%M')})."
        )[:300]
        alert = LateAlert.objects.create(assignment=assignment, message=msg)
        send_push_to_admins(
            "Alerte fin de service SMS",
            alert.message,
            {"alert_id": str(alert.id), "site": assignment.site.name, "type": "fin_sans_pointage"},
        )

    # Absence : créneau terminé, aucune prise de service (y compris après dépêche non honorée).
    for assignment in (
        ShiftAssignment.objects.filter(
            shift_date=today,
            status__in=[ShiftAssignment.Status.SCHEDULED, ShiftAssignment.Status.REPLACED],
        )
        .select_related("site", "guard")
        .iterator()
    ):
        has_start = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists()
        if has_start:
            continue
        deadline = _aware_at(
            assignment.site,
            assignment.shift_date,
            assignment.end_time,
            assignment.site.late_tolerance_minutes,
        )
        if now <= deadline:
            continue
        absence_exists = LateAlert.objects.filter(
            assignment=assignment,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="Absence:",
        ).exists()
        if absence_exists:
            continue
        msg = (
            f"Absence: créneau terminé sans prise de service — {assignment.guard.display_name} @ "
            f"{assignment.site.name} (fin prévue {assignment.end_time.strftime('%H:%M')})."
        )[:300]
        alert = LateAlert.objects.create(assignment=assignment, message=msg)
        send_push_to_admins(
            "Alerte absence SMS",
            alert.message,
            {"alert_id": str(alert.id), "site": assignment.site.name, "type": "absence"},
        )
        ShiftAssignment.objects.filter(pk=assignment.pk).update(status=ShiftAssignment.Status.MISSED)
