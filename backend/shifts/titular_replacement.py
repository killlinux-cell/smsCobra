"""Promotion du remplaçant en titulaire sur poste fixe après dépêche (absence titulaire)."""

from __future__ import annotations

from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from shifts.models import FixedPost, ShiftAssignment
from shifts.services import _slot_for


def shift_type_for_assignment(assignment: ShiftAssignment) -> str | None:
    if assignment.start_time == time(6, 0):
        return FixedPost.ShiftType.DAY
    if assignment.start_time == time(18, 0):
        return FixedPost.ShiftType.NIGHT
    return None


def find_fixed_post_for_assignment(assignment: ShiftAssignment) -> FixedPost | None:
    shift_type = shift_type_for_assignment(assignment)
    if not shift_type:
        return None
    return (
        FixedPost.objects.select_for_update()
        .filter(
            site_id=assignment.site_id,
            shift_type=shift_type,
            is_active=True,
        )
        .first()
    )


def sync_scheduled_assignments_for_titular(post: FixedPost, from_date: date) -> int:
    """Aligne les affectations planifiées futures sur le titulaire actuel du poste fixe."""
    start_time, end_time = _slot_for(post.shift_type)
    updated = (
        ShiftAssignment.objects.filter(
            site_id=post.site_id,
            start_time=start_time,
            shift_date__gte=from_date,
            status=ShiftAssignment.Status.SCHEDULED,
        )
        .exclude(guard_id=post.titular_guard_id)
        .update(
            guard_id=post.titular_guard_id,
            original_guard_id=None,
            end_time=end_time,
        )
    )
    return updated


@transaction.atomic
def promote_replacement_to_titular_on_dispatch(
    assignment: ShiftAssignment,
    *,
    absent_guard_id: int,
    replacement_guard_id: int,
    actor=None,
) -> FixedPost | None:
    """
    Si le vigile absent est titulaire du poste fixe (jour/nuit) du site,
    le remplaçant devient titulaire ; l'absent est suspendu jusqu'à réintégration.
    """
    post = find_fixed_post_for_assignment(assignment)
    if not post or post.titular_guard_id != absent_guard_id:
        return None
    if post.suspended_titular_guard_id:
        raise ValidationError(
            "Un titulaire est déjà suspendu sur ce poste. Repositionnez-le avant une nouvelle dépêche."
        )

    post.suspended_titular_guard_id = absent_guard_id
    post.titular_guard_id = replacement_guard_id
    post.replacement_guard_id = None
    post.replacement_active = False
    post.suspended_at = timezone.now()
    post.suspension_reason = ""
    post.save(
        update_fields=[
            "suspended_titular_guard_id",
            "titular_guard_id",
            "replacement_guard_id",
            "replacement_active",
            "suspended_at",
            "suspension_reason",
            "updated_at",
        ]
    )
    sync_scheduled_assignments_for_titular(post, assignment.shift_date)

    from django.contrib.auth import get_user_model
    from reports.titular_changes import log_titular_promotion

    User = get_user_model()
    absent_guard = User.objects.filter(pk=absent_guard_id).first()
    new_titular = User.objects.filter(pk=replacement_guard_id).first()
    if absent_guard and new_titular:
        log_titular_promotion(
            fixed_post=post,
            assignment=assignment,
            absent_guard=absent_guard,
            new_titular_guard=new_titular,
            actor=actor,
        )
    return post


@transaction.atomic
def reinstate_suspended_titular(
    fixed_post: FixedPost,
    *,
    reason: str,
    actor=None,
) -> FixedPost:
    """Réintègre le titulaire suspendu (action superviseur)."""
    reason = (reason or "").strip()
    if not fixed_post.suspended_titular_guard_id:
        raise ValidationError("Aucun titulaire suspendu sur ce poste.")
    if len(reason) < 10:
        raise ValidationError(
            "Indiquez un motif valable d'au moins 10 caractères (justification de l'absence)."
        )

    reinstated_id = fixed_post.suspended_titular_guard_id
    former_interim = fixed_post.titular_guard
    reinstated_guard = fixed_post.suspended_titular_guard
    fixed_post.titular_guard_id = reinstated_id
    fixed_post.suspended_titular_guard_id = None
    fixed_post.suspension_reason = reason
    fixed_post.suspended_at = None
    fixed_post.replacement_guard_id = None
    fixed_post.replacement_active = False
    fixed_post.save(
        update_fields=[
            "titular_guard_id",
            "suspended_titular_guard_id",
            "suspension_reason",
            "suspended_at",
            "replacement_guard_id",
            "replacement_active",
            "updated_at",
        ]
    )
    sync_scheduled_assignments_for_titular(fixed_post, timezone.localdate())

    if reinstated_guard:
        from reports.titular_changes import log_titular_reinstatement

        log_titular_reinstatement(
            fixed_post=fixed_post,
            reinstated_guard=reinstated_guard,
            former_titular_guard=former_interim,
            reason=reason,
            actor=actor,
        )
    return fixed_post
