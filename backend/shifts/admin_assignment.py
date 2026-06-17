"""Création / mise à jour d'affectations (API admin mobile, aligné webadmin)."""

from __future__ import annotations

from datetime import date, time, timedelta

from django.core.exceptions import ValidationError

from accounts.models import User
from shifts.guard_conflicts import (
    conflict_error_message,
    find_assignment_conflict_on_other_site,
    find_titular_fixed_post_on_other_site,
    titular_conflict_error_message,
)
from shifts.models import FixedPost, ShiftAssignment
from shifts.slot_occupancy import (
    count_occupying_assignments,
    has_blocking_assignment_for_new_titular,
    purge_orphaned_scheduled_for_slot,
)
from sites.models import Site

from shifts.site_shift_times import (
    SHIFT_DAY,
    SHIFT_NIGHT,
    incoming_relief_lookup,
    opposite_passation_slot,
    slot_times_for_site,
)

MODE_PLANIFIER = "planifier"
MODE_EXTRA = "extra"


def slot_times(site: Site, shift_type: str) -> tuple[time, time]:
    return slot_times_for_site(site, shift_type)


def fixed_post_shift_type(shift_type: str) -> str:
    return FixedPost.ShiftType.DAY if shift_type == SHIFT_DAY else FixedPost.ShiftType.NIGHT


def apply_times_and_relief(obj: ShiftAssignment, shift_type: str) -> None:
    start_time, end_time = slot_times(obj.site, shift_type)
    obj.start_time = start_time
    obj.end_time = end_time
    incoming_date, incoming_start = incoming_relief_lookup(
        obj.site, shift_type, obj.shift_date
    )
    obj.relieved_by = ShiftAssignment.objects.filter(
        site=obj.site,
        shift_date=incoming_date,
        start_time=incoming_start,
    ).first()


def ensure_fixed_post(obj: ShiftAssignment, shift_type: str) -> None:
    fp_shift = fixed_post_shift_type(shift_type)
    existing = FixedPost.objects.filter(
        site=obj.site,
        shift_type=fp_shift,
        is_active=True,
        titular_guard=obj.guard,
    ).first()
    if existing:
        if not existing.start_date and obj.shift_date:
            existing.start_date = obj.shift_date
            existing.save(update_fields=["start_date", "updated_at"])
        return
    required = obj.site.staff_required_for_shift(shift_type)
    active_count = FixedPost.objects.filter(
        site=obj.site,
        shift_type=fp_shift,
        is_active=True,
    ).count()
    if active_count >= required:
        raise ValidationError(
            f"Effectif titulaire déjà complet ({required}) pour ce site en "
            f"{'jour' if fp_shift == FixedPost.ShiftType.DAY else 'nuit'}."
        )
    FixedPost.objects.create(
        site=obj.site,
        shift_type=fp_shift,
        titular_guard=obj.guard,
        is_active=True,
        start_date=obj.shift_date,
    )


def _validate_common_slot(
    *,
    site: Site,
    guard: User,
    shift_date: date,
    shift_type: str,
    exclude_pk: int | None = None,
) -> tuple[time, time]:
    start_time, end_time = slot_times(site, shift_type)

    opposite_date, opposite_start = opposite_passation_slot(site, shift_type, shift_date)
    opposite = ShiftAssignment.objects.filter(
        site=site,
        shift_date=opposite_date,
        start_time=opposite_start,
        guard=guard,
    )
    if exclude_pk:
        opposite = opposite.exclude(pk=exclude_pk)
    if opposite.exists():
        raise ValidationError(
            "Ce vigile est déjà affecté au poste opposé autour de cette passation. "
            "Choisissez un autre vigile."
        )

    conflict = find_assignment_conflict_on_other_site(
        guard_id=guard.pk,
        site_id=site.pk,
        shift_date=shift_date,
        start_time=start_time,
        exclude_assignment_id=exclude_pk,
    )
    if conflict:
        raise ValidationError(conflict_error_message(conflict))

    return start_time, end_time


def validate_create_assignment(
    *,
    guard: User,
    site: Site,
    shift_date: date,
    shift_type: str,
    planning_mode: str = MODE_PLANIFIER,
    extra_days: int = 1,
    create_fixed_post: bool = True,
) -> None:
    start_time, _end_time = _validate_common_slot(
        site=site,
        guard=guard,
        shift_date=shift_date,
        shift_type=shift_type,
    )

    if planning_mode == MODE_EXTRA:
        if extra_days < 1 or extra_days > 31:
            raise ValidationError("Indiquez une durée Extra entre 1 et 31 jours.")
        fp_shift = fixed_post_shift_type(shift_type)
        titular_post = FixedPost.objects.filter(
            site=site,
            shift_type=fp_shift,
            is_active=True,
        ).first()
        if not titular_post or not titular_post.titular_guard_id:
            raise ValidationError(
                "Un titulaire doit déjà être en place sur ce site (poste jour ou nuit) "
                "avant d'ajouter un vigile Extra."
            )
        if titular_post.titular_guard_id == guard.pk:
            raise ValidationError(
                "Le vigile Extra doit être différent du titulaire actuel du poste."
            )
        for offset in range(extra_days):
            day = shift_date + timedelta(days=offset)
            if ShiftAssignment.objects.filter(
                site=site,
                shift_date=day,
                start_time=start_time,
                guard=guard,
            ).exists():
                raise ValidationError(
                    f"Ce vigile a déjà une affectation sur ce créneau le {day.strftime('%d/%m/%Y')}."
                )
            conflict = find_assignment_conflict_on_other_site(
                guard_id=guard.pk,
                site_id=site.pk,
                shift_date=day,
                start_time=start_time,
            )
            if conflict:
                raise ValidationError(conflict_error_message(conflict))
        return

    same_slot = ShiftAssignment.objects.filter(
        site=site,
        shift_date=shift_date,
        start_time=start_time,
    )
    fp_shift = fixed_post_shift_type(shift_type)
    required = site.staff_required_for_shift(shift_type)
    active_posts = FixedPost.objects.filter(
        site=site,
        shift_type=fp_shift,
        is_active=True,
    ).count()
    if active_posts < required:
        purge_orphaned_scheduled_for_slot(
            site_id=site.pk,
            shift_type=fp_shift,
            from_date=shift_date,
        )
    occupying = count_occupying_assignments(
        site_id=site.pk,
        shift_date=shift_date,
        start_time=start_time,
        shift_type=fp_shift,
    )
    if occupying >= required:
        raise ValidationError(
            f"Effectif cible atteint pour ce site ({required} poste(s) "
            f"{'jour' if shift_type == SHIFT_DAY else 'nuit'}). "
            "Utilisez le mode Extra pour un renfort temporaire."
        )
    if has_blocking_assignment_for_new_titular(
        site_id=site.pk,
        shift_date=shift_date,
        start_time=start_time,
        shift_type=fp_shift,
        guard_id=guard.pk,
    ):
        raise ValidationError(
            "Ce poste (jour/nuit) est déjà attribué pour ce site et cette date."
        )

    if create_fixed_post:
        fp_shift = fixed_post_shift_type(shift_type)
        titular_elsewhere = find_titular_fixed_post_on_other_site(
            guard_id=guard.pk,
            site_id=site.pk,
            shift_type=fp_shift,
        )
        if titular_elsewhere:
            raise ValidationError(titular_conflict_error_message(titular_elsewhere))


def create_assignment(
    *,
    guard: User,
    site: Site,
    shift_date: date,
    shift_type: str,
    planning_mode: str = MODE_PLANIFIER,
    extra_days: int = 1,
    create_fixed_post: bool = True,
) -> ShiftAssignment | list[ShiftAssignment]:
    validate_create_assignment(
        guard=guard,
        site=site,
        shift_date=shift_date,
        shift_type=shift_type,
        planning_mode=planning_mode,
        extra_days=extra_days,
        create_fixed_post=create_fixed_post,
    )
    start_time, end_time = slot_times(site, shift_type)

    if planning_mode == MODE_EXTRA:
        created: list[ShiftAssignment] = []
        for offset in range(extra_days):
            day = shift_date + timedelta(days=offset)
            assignment = ShiftAssignment.objects.create(
                guard=guard,
                site=site,
                shift_date=day,
                start_time=start_time,
                end_time=end_time,
                status=ShiftAssignment.Status.EXTRA,
                relieved_by=None,
            )
            created.append(assignment)
        return created

    assignment = ShiftAssignment(
        guard=guard,
        site=site,
        shift_date=shift_date,
        start_time=start_time,
        end_time=end_time,
        status=ShiftAssignment.Status.SCHEDULED,
    )
    apply_times_and_relief(assignment, shift_type)
    assignment.save()
    if create_fixed_post:
        ensure_fixed_post(assignment, shift_type)
    return assignment


def update_assignment(
    instance: ShiftAssignment,
    *,
    guard: User,
    site: Site,
    shift_date: date,
    shift_type: str,
) -> ShiftAssignment:
    start_time, _end_time = _validate_common_slot(
        site=site,
        guard=guard,
        shift_date=shift_date,
        shift_type=shift_type,
        exclude_pk=instance.pk,
    )
    same_slot = ShiftAssignment.objects.filter(
        site=site,
        shift_date=shift_date,
        start_time=start_time,
    ).exclude(pk=instance.pk)
    if same_slot.exists():
        raise ValidationError(
            "Ce poste (jour/nuit) est déjà attribué pour ce site et cette date."
        )

    instance.guard = guard
    instance.site = site
    instance.shift_date = shift_date
    apply_times_and_relief(instance, shift_type)
    instance.save()
    return instance
