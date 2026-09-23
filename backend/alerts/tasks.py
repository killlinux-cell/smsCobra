from datetime import date, timedelta

from celery import shared_task
from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone

from checkins.models import Checkin
from checkins.window import end_checkin_deadline, start_checkin_deadline
from reports.attendance import refresh_attendance_report
from shifts.models import ShiftAssignment
from shifts.services import ensure_assignments_for_dates

from .models import LateAlert
from .services import send_push_to_admins, resolve_stale_fin_sans_pointage_alerts

# Fenêtre glissante : ne pas rescanner tout l'historique à chaque passage Celery.
_RECENT_ASSIGNMENT_LOOKBACK_DAYS = 2
_SCAN_LOCK_KEY = "cobra:detect_missed_lock"
_SCAN_LOCK_SEC = 240


def _recent_assignment_dates(today: date) -> list[date]:
    return [today - timedelta(days=offset) for offset in range(_RECENT_ASSIGNMENT_LOOKBACK_DAYS + 1)]


def _checkin_type_sets(assignment_ids: list[int]) -> tuple[set[int], set[int]]:
    starts: set[int] = set()
    ends: set[int] = set()
    if not assignment_ids:
        return starts, ends
    for assignment_id, check_type in Checkin.objects.filter(
        assignment_id__in=assignment_ids,
        type__in=[Checkin.Type.START, Checkin.Type.END],
    ).values_list("assignment_id", "type"):
        if check_type == Checkin.Type.START:
            starts.add(assignment_id)
        else:
            ends.add(assignment_id)
    return starts, ends


def _alert_assignment_ids(assignment_ids: list[int], prefix: str) -> set[int]:
    if not assignment_ids:
        return set()
    return set(
        LateAlert.objects.filter(
            assignment_id__in=assignment_ids,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith=prefix,
        ).values_list("assignment_id", flat=True)
    )


@shared_task
def detect_missed_shift_task():
    from reports.alert_ack import supervisor_decided_assignment_ids
    from shifts.site_shift_times import assignment_is_operational

    if not cache.add(_SCAN_LOCK_KEY, 1, timeout=_SCAN_LOCK_SEC):
        return

    try:
        _run_missed_shift_scan(assignment_is_operational, supervisor_decided_assignment_ids)
    finally:
        cache.delete(_SCAN_LOCK_KEY)


def _run_missed_shift_scan(assignment_is_operational, supervisor_decided_assignment_ids) -> None:
    now = timezone.now()
    today = timezone.localdate()
    ensure_assignments_for_dates([today, today + timedelta(days=1)])

    active_statuses = ShiftAssignment.active_on_duty_statuses()
    today_assignments = list(
        ShiftAssignment.objects.select_related("site", "guard").filter(
            shift_date=today,
            status__in=active_statuses,
        )
    )
    today_ids = [a.pk for a in today_assignments]
    start_ids, end_ids = _checkin_type_sets(today_ids)
    decided_ids = supervisor_decided_assignment_ids(today_assignments)
    retard_alert_ids = _alert_assignment_ids(today_ids, "Retard prise de service :")
    passation_alert_ids = _alert_assignment_ids(today_ids, "Passation:")
    absence_alert_ids = _alert_assignment_ids(today_ids, "Absence:")

    for assignment in today_assignments:
        if not assignment_is_operational(assignment):
            continue
        if assignment.pk in decided_ids:
            continue
        deadline = start_checkin_deadline(
            assignment,
            tolerance_minutes=assignment.site.late_tolerance_minutes,
        )
        if now > deadline and assignment.pk not in start_ids and assignment.pk not in retard_alert_ids:
            alert = LateAlert.objects.create(
                assignment=assignment,
                message=(
                    f"Retard prise de service : {assignment.guard.username} sur {assignment.site.name}"
                ),
            )
            retard_alert_ids.add(assignment.pk)
            send_push_to_admins(
                "Alerte retard SMS",
                alert.message,
                {"alert_id": str(alert.id), "site": assignment.site.name},
            )

    incoming_qs = (
        ShiftAssignment.objects.filter(
            shift_date=today,
            status__in=active_statuses,
            outgoing_handover_assignments__isnull=False,
        )
        .select_related("site", "guard")
        .prefetch_related(
            Prefetch(
                "outgoing_handover_assignments",
                queryset=ShiftAssignment.objects.select_related("guard"),
            )
        )
        .distinct()
    )
    for incoming in incoming_qs:
        if not assignment_is_operational(incoming):
            continue
        if incoming.pk in decided_ids:
            continue
        grace = incoming.site.relief_late_alert_minutes
        deadline = start_checkin_deadline(incoming, tolerance_minutes=grace)
        if now > deadline and incoming.pk not in start_ids and incoming.pk not in passation_alert_ids:
            outgoing = incoming.outgoing_handover_assignments.first()
            msg = (
                f"Passation: le releve {incoming.guard.username} n'a pas pris son service sur "
                f"{incoming.site.name} (prevu {incoming.start_time.strftime('%H:%M')}, "
                f"depasse de plus de {grace} min). Vigile en poste : {outgoing.guard.username if outgoing else 'N/A'}."
            )
            alert = LateAlert.objects.create(assignment=incoming, message=msg[:300])
            passation_alert_ids.add(incoming.pk)
            send_push_to_admins(
                "Alerte passation SMS",
                alert.message,
                {"alert_id": str(alert.id), "site": incoming.site.name, "type": "passation"},
            )

    resolve_stale_fin_sans_pointage_alerts()
    recent_dates = _recent_assignment_dates(today)
    recent_assignments = list(
        ShiftAssignment.objects.filter(
            shift_date__in=recent_dates,
            status__in=active_statuses,
        ).select_related("site", "guard")
    )
    recent_ids = [a.pk for a in recent_assignments]
    recent_starts, recent_ends = _checkin_type_sets(recent_ids)
    fin_alert_ids = _alert_assignment_ids(recent_ids, "FinSansPointage:")

    for assignment in recent_assignments:
        if assignment.pk not in recent_starts or assignment.pk in recent_ends:
            continue
        deadline = end_checkin_deadline(
            assignment,
            tolerance_minutes=assignment.site.late_tolerance_minutes,
        )
        if now <= deadline or assignment.pk in fin_alert_ids:
            continue
        msg = (
            f"FinSansPointage: fin non pointée — {assignment.guard.display_name} @ {assignment.site.name} "
            f"(fin prévue {assignment.end_time.strftime('%H:%M')})."
        )[:300]
        alert = LateAlert.objects.create(assignment=assignment, message=msg)
        fin_alert_ids.add(assignment.pk)
        send_push_to_admins(
            "Alerte fin de service SMS",
            alert.message,
            {"alert_id": str(alert.id), "site": assignment.site.name, "type": "fin_sans_pointage"},
        )
        refresh_attendance_report(assignment, now=now)

    for assignment in today_assignments:
        if not assignment_is_operational(assignment):
            continue
        if assignment.pk in decided_ids:
            continue
        if assignment.pk in start_ids:
            continue
        deadline = end_checkin_deadline(
            assignment,
            tolerance_minutes=assignment.site.late_tolerance_minutes,
        )
        if now <= deadline or assignment.pk in absence_alert_ids:
            continue
        msg = (
            f"Absence: créneau terminé sans prise de service — {assignment.guard.display_name} @ "
            f"{assignment.site.name} (fin prévue {assignment.end_time.strftime('%H:%M')})."
        )[:300]
        alert = LateAlert.objects.create(assignment=assignment, message=msg)
        absence_alert_ids.add(assignment.pk)
        send_push_to_admins(
            "Alerte absence SMS",
            alert.message,
            {"alert_id": str(alert.id), "site": assignment.site.name, "type": "absence"},
        )
        ShiftAssignment.objects.filter(pk=assignment.pk).update(status=ShiftAssignment.Status.MISSED)
        refresh_attendance_report(assignment, now=now)
