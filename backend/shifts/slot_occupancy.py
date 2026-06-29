"""Occupation des créneaux jour/nuit (postes fixes + affectations planifiées)."""

from __future__ import annotations

from datetime import date, time

from shifts.models import FixedPost, ShiftAssignment
from shifts.site_shift_times import shift_type_for_start_time, slot_times_for_site
from sites.models import Site


def fixed_post_shift_type_for_start(site: Site, start_time: time) -> str | None:
    return shift_type_for_start_time(site, start_time)


def active_titular_guard_ids(*, site_id: int, shift_type: str) -> set[int]:
    ids: set[int] = set()
    for fp in FixedPost.objects.filter(
        site_id=site_id,
        shift_type=shift_type,
        is_active=True,
    ).only(
        "titular_guard_id",
        "replacement_guard_id",
        "replacement_active",
    ):
        if fp.titular_guard_id:
            ids.add(fp.titular_guard_id)
        if fp.replacement_active and fp.replacement_guard_id:
            ids.add(fp.replacement_guard_id)
    return ids


def assignment_occupies_titular_slot(assignment: ShiftAssignment, active_titular_ids: set[int]) -> bool:
    """True si l'affectation occupe réellement un slot titulaire (pas une planification orpheline)."""
    if assignment.status == ShiftAssignment.Status.EXTRA:
        return False
    if assignment.status != ShiftAssignment.Status.SCHEDULED:
        return True
    return assignment.guard_id in active_titular_ids


def count_occupying_assignments(
    *,
    site_id: int,
    shift_date: date,
    start_time: time,
    shift_type: str,
) -> int:
    active_ids = active_titular_guard_ids(site_id=site_id, shift_type=shift_type)
    qs = ShiftAssignment.objects.filter(
        site_id=site_id,
        shift_date=shift_date,
        start_time=start_time,
    ).exclude(status=ShiftAssignment.Status.EXTRA)
    return sum(
        1 for row in qs.only("guard_id", "status") if assignment_occupies_titular_slot(row, active_ids)
    )


def has_blocking_assignment_for_new_titular(
    *,
    site_id: int,
    shift_date: date,
    start_time: time,
    shift_type: str,
    guard_id: int,
) -> bool:
    """True si ce vigile a déjà une affectation sur ce créneau (site + date + heure)."""
    return (
        ShiftAssignment.objects.filter(
            site_id=site_id,
            shift_date=shift_date,
            start_time=start_time,
            guard_id=guard_id,
        )
        .exclude(status=ShiftAssignment.Status.EXTRA)
        .exists()
    )


def purge_orphaned_scheduled_for_slot(
    *,
    site_id: int,
    shift_type: str,
    from_date: date,
) -> int:
    """
    Supprime les affectations planifiées laissées par un titulaire retiré
    (poste fixe nuit/jour inactif ou vigile plus titulaire actif).
    """
    site = Site.objects.filter(pk=site_id).only("expected_start_time", "expected_end_time").first()
    if not site:
        return 0
    start_time, _ = slot_times_for_site(site, shift_type)
    active_ids = active_titular_guard_ids(site_id=site_id, shift_type=shift_type)
    qs = ShiftAssignment.objects.filter(
        site_id=site_id,
        start_time=start_time,
        shift_date__gte=from_date,
        status=ShiftAssignment.Status.SCHEDULED,
    )
    if active_ids:
        qs = qs.exclude(guard_id__in=active_ids)
    delete_ids = list(qs.values_list("pk", flat=True))
    if not delete_ids:
        return 0
    deleted, _ = ShiftAssignment.objects.filter(pk__in=delete_ids).delete()
    return deleted
