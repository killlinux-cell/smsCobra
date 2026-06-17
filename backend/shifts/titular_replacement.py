"""Promotion du remplaçant en titulaire sur poste fixe après dépêche (absence titulaire)."""

from __future__ import annotations

from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from shifts.models import FixedPost, ShiftAssignment
from shifts.site_shift_times import shift_type_for_start_time
from shifts.services import _slot_for


def shift_type_for_assignment(assignment: ShiftAssignment) -> str | None:
    return shift_type_for_start_time(assignment.site, assignment.start_time)


def find_fixed_post_for_assignment(
    assignment: ShiftAssignment,
    *,
    titular_guard_id: int | None = None,
) -> FixedPost | None:
    shift_type = shift_type_for_assignment(assignment)
    if not shift_type:
        return None
    qs = FixedPost.objects.select_for_update().filter(
        site_id=assignment.site_id,
        shift_type=shift_type,
        is_active=True,
    )
    if titular_guard_id:
        qs = qs.filter(titular_guard_id=titular_guard_id)
    return qs.first()


def _deactivate_conflicting_titular_posts(post: FixedPost, titular_guard_id: int) -> int:
    """Évite le conflit d'unicité site+créneau+titulaire sur plusieurs postes actifs."""
    today = timezone.localdate()
    return FixedPost.objects.filter(
        site_id=post.site_id,
        shift_type=post.shift_type,
        titular_guard_id=titular_guard_id,
        is_active=True,
    ).exclude(pk=post.pk).update(
        is_active=False,
        end_date=today,
        updated_at=timezone.now(),
    )


def sync_scheduled_assignments_for_titular(
    post: FixedPost,
    from_date: date,
    *,
    previous_guard_id: int | None = None,
) -> int:
    """Aligne les affectations planifiées futures sur le titulaire actuel du poste fixe."""
    start_time, end_time = _slot_for(post)
    qs = ShiftAssignment.objects.filter(
        site_id=post.site_id,
        start_time=start_time,
        shift_date__gte=from_date,
        status=ShiftAssignment.Status.SCHEDULED,
    )
    if previous_guard_id:
        to_reassign = list(qs.filter(guard_id=previous_guard_id))
    else:
        to_reassign = list(qs.exclude(guard_id=post.titular_guard_id))

    target_id = post.titular_guard_id
    moved = 0
    for row in to_reassign:
        conflict = (
            ShiftAssignment.objects.filter(
                site_id=post.site_id,
                shift_date=row.shift_date,
                start_time=start_time,
                guard_id=target_id,
            )
            .exclude(pk=row.pk)
            .first()
        )
        if conflict:
            if conflict.status == ShiftAssignment.Status.SCHEDULED:
                row.delete()
                continue
        ShiftAssignment.objects.filter(pk=row.pk).update(
            guard_id=target_id,
            original_guard_id=None,
            end_time=end_time,
        )
        moved += 1
    return moved


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
    post = find_fixed_post_for_assignment(assignment, titular_guard_id=absent_guard_id)
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
    _deactivate_conflicting_titular_posts(post, replacement_guard_id)
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
    sync_scheduled_assignments_for_titular(
        post,
        assignment.shift_date,
        previous_guard_id=absent_guard_id,
    )

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
    _deactivate_conflicting_titular_posts(fixed_post, reinstated_id)
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
    sync_scheduled_assignments_for_titular(
        fixed_post,
        timezone.localdate(),
        previous_guard_id=former_interim.id if former_interim else None,
    )

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


@transaction.atomic
def dismiss_suspended_titular(
    fixed_post: FixedPost,
    *,
    reason: str,
    actor=None,
) -> FixedPost:
    """Libère le titulaire suspendu sans le réintégrer (le titulaire actuel reste en place)."""
    reason = (reason or "").strip()
    if not fixed_post.suspended_titular_guard_id:
        raise ValidationError("Aucun titulaire suspendu sur ce poste.")
    if len(reason) < 10:
        raise ValidationError(
            "Indiquez un motif d'au moins 10 caractères (fin de titularité / mutation)."
        )
    fixed_post.suspension_reason = reason
    fixed_post.suspended_titular_guard_id = None
    fixed_post.suspended_at = None
    fixed_post.save(
        update_fields=[
            "suspension_reason",
            "suspended_titular_guard_id",
            "suspended_at",
            "updated_at",
        ]
    )
    return fixed_post


def _cancel_scheduled_assignments_for_retired_post(
    post: FixedPost,
    *,
    from_date: date,
    guard_id: int | None = None,
) -> int:
    """Supprime les affectations planifiées à partir de from_date (sauf créneau en cours pointé)."""
    from checkins.models import Checkin

    start_time, _ = _slot_for(post)
    target_guard_id = guard_id or post.titular_guard_id
    qs = ShiftAssignment.objects.filter(
        site_id=post.site_id,
        start_time=start_time,
        guard_id=target_guard_id,
        shift_date__gte=from_date,
        status=ShiftAssignment.Status.SCHEDULED,
    )
    delete_ids: list[int] = []
    for assignment in qs.only("id", "shift_date"):
        if assignment.shift_date == from_date:
            has_start = Checkin.objects.filter(
                assignment_id=assignment.id,
                type=Checkin.Type.START,
            ).exists()
            if has_start:
                continue
        delete_ids.append(assignment.id)
    if not delete_ids:
        return 0
    deleted, _ = ShiftAssignment.objects.filter(pk__in=delete_ids).delete()
    return deleted


@transaction.atomic
def retire_titular_fixed_post(
    fixed_post: FixedPost,
    *,
    reason: str,
    actor=None,
    from_date: date | None = None,
    clear_suspended: bool = False,
) -> tuple[FixedPost, int]:
    """Retire un titulaire : poste fixe inactif + plus d'affectations planifiées futures."""
    reason = (reason or "").strip()
    if not fixed_post.is_active:
        raise ValidationError("Ce poste fixe est déjà inactif.")
    if fixed_post.suspended_titular_guard_id and not clear_suspended:
        raise ValidationError(
            "Un titulaire est suspendu sur ce poste. Réintégrez-le, libérez-le sans réintégration, "
            "ou cochez « Ne pas réintégrer l'ancien titulaire »."
        )
    if len(reason) < 10:
        raise ValidationError(
            "Indiquez un motif d'au moins 10 caractères "
            "(réduction d'effectif, mutation, fin de contrat, etc.)."
        )

    effective_from = from_date or timezone.localdate()
    retired_guard = fixed_post.titular_guard
    cancelled = _cancel_scheduled_assignments_for_retired_post(
        fixed_post,
        from_date=effective_from,
    )

    if clear_suspended:
        fixed_post.suspended_titular_guard_id = None
        fixed_post.suspended_at = None

    fixed_post.is_active = False
    fixed_post.end_date = effective_from
    fixed_post.replacement_guard_id = None
    fixed_post.replacement_active = False
    fixed_post.save(
        update_fields=[
            "is_active",
            "end_date",
            "replacement_guard_id",
            "replacement_active",
            "suspended_titular_guard_id",
            "suspended_at",
            "updated_at",
        ]
    )

    if retired_guard:
        from reports.titular_changes import log_titular_retirement

        log_titular_retirement(
            fixed_post=fixed_post,
            retired_guard=retired_guard,
            reason=reason,
            actor=actor,
        )
    return fixed_post, cancelled
