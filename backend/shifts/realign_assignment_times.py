"""Recaler les horaires planifiés sur ceux définis sur chaque site (sans toucher le passé)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from checkins.models import Checkin
from shifts.models import ShiftAssignment
from shifts.services import ensure_assignments_for_dates
from shifts.site_shift_times import (
    _LEGACY_DAY_START,
    _LEGACY_NIGHT_START,
    day_slot_times,
    night_slot_times,
    shift_type_for_start_time,
    slot_times_for_site,
)


@dataclass
class RealignRow:
    assignment_id: int
    site_name: str
    shift_date: date
    guard_id: int
    shift_type: str
    old_start: str
    old_end: str
    new_start: str
    new_end: str
    reason: str


@dataclass
class RealignResult:
    candidates: list[RealignRow]
    skipped_has_start: int
    skipped_unknown_slot: int
    skipped_already_ok: int
    skipped_not_legacy: int
    applied: int
    relieved_by_reset: int


def _fmt(t) -> str:
    return t.strftime("%H:%M")


def _site_uses_legacy_hours(site) -> bool:
    day_start, day_end = day_slot_times(site)
    night_start, night_end = night_slot_times(site)
    return (
        day_start == _LEGACY_DAY_START
        and day_end == _LEGACY_NIGHT_START
        and night_start == _LEGACY_NIGHT_START
        and night_end == _LEGACY_DAY_START
    )


def plan_realign_scheduled_assignment_times(
    *,
    from_date: date | None = None,
    site_id: int | None = None,
) -> RealignResult:
    """
    Repère les affectations planifiées futures encore en 06:00/18:00 fixes
    alors que le site a d'autres horaires attendus.
    """
    filter_day = from_date or timezone.localdate()
    qs = (
        ShiftAssignment.objects.filter(
            status=ShiftAssignment.Status.SCHEDULED,
            shift_date__gte=filter_day,
        )
        .select_related("site", "guard")
        .order_by("site__name", "shift_date", "start_time")
    )
    if site_id:
        qs = qs.filter(site_id=site_id)

    assignment_ids = list(qs.values_list("pk", flat=True))
    started_ids = set(
        Checkin.objects.filter(
            assignment_id__in=assignment_ids,
            type=Checkin.Type.START,
        ).values_list("assignment_id", flat=True)
    )

    candidates: list[RealignRow] = []
    skipped_has_start = 0
    skipped_unknown_slot = 0
    skipped_already_ok = 0
    skipped_not_legacy = 0

    for assignment in qs.iterator(chunk_size=200):
        if assignment.pk in started_ids:
            skipped_has_start += 1
            continue

        shift_type = shift_type_for_start_time(assignment.site, assignment.start_time)
        if shift_type is None:
            skipped_unknown_slot += 1
            continue

        new_start, new_end = slot_times_for_site(assignment.site, shift_type)
        if assignment.start_time == new_start and assignment.end_time == new_end:
            skipped_already_ok += 1
            continue

        if _site_uses_legacy_hours(assignment.site):
            skipped_not_legacy += 1
            continue

        # Conservateur : ne recale que les créneaux encore aux heures fixes historiques.
        if assignment.start_time not in (_LEGACY_DAY_START, _LEGACY_NIGHT_START):
            skipped_not_legacy += 1
            continue

        candidates.append(
            RealignRow(
                assignment_id=assignment.pk,
                site_name=assignment.site.name,
                shift_date=assignment.shift_date,
                guard_id=assignment.guard_id,
                shift_type=shift_type,
                old_start=_fmt(assignment.start_time),
                old_end=_fmt(assignment.end_time),
                new_start=_fmt(new_start),
                new_end=_fmt(new_end),
                reason="legacy_6h_18h",
            )
        )

    return RealignResult(
        candidates=candidates,
        skipped_has_start=skipped_has_start,
        skipped_unknown_slot=skipped_unknown_slot,
        skipped_already_ok=skipped_already_ok,
        skipped_not_legacy=skipped_not_legacy,
        applied=0,
        relieved_by_reset=0,
    )


def apply_realign_scheduled_assignment_times(
    *,
    from_date: date | None = None,
    site_id: int | None = None,
) -> RealignResult:
    plan = plan_realign_scheduled_assignment_times(from_date=from_date, site_id=site_id)
    if not plan.candidates:
        return plan

    affected_days: set[date] = set()
    updated_ids: list[int] = []

    for row in plan.candidates:
        assignment = ShiftAssignment.objects.select_related("site").get(pk=row.assignment_id)
        new_start, new_end = slot_times_for_site(assignment.site, row.shift_type)
        ShiftAssignment.objects.filter(pk=assignment.pk).update(
            start_time=new_start,
            end_time=new_end,
            relieved_by=None,
        )
        updated_ids.append(assignment.pk)
        affected_days.add(assignment.shift_date)
        if row.shift_type == "night":
            affected_days.add(assignment.shift_date + timedelta(days=1))

    # Relie les passations jour/nuit avec les nouvelles heures.
    if affected_days:
        ensure_assignments_for_dates(sorted(affected_days))

    plan.applied = len(updated_ids)
    plan.relieved_by_reset = len(updated_ids)
    return plan
