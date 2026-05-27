"""Détection des conflits d'affectation : un vigile ne peut pas tenir le même créneau sur deux sites."""

from __future__ import annotations

from datetime import date, time

from shifts.models import FixedPost, ShiftAssignment


def _active_assignment_qs():
    return ShiftAssignment.objects.filter(
        status__in=ShiftAssignment.active_on_duty_statuses(),
    ).select_related("site")


def find_assignment_conflict_on_other_site(
    *,
    guard_id: int,
    site_id: int,
    shift_date: date,
    start_time: time,
    exclude_assignment_id: int | None = None,
) -> ShiftAssignment | None:
    """Retourne une affectation active du vigile sur un autre site, même date et même créneau."""
    qs = _active_assignment_qs().filter(
        guard_id=guard_id,
        shift_date=shift_date,
        start_time=start_time,
    ).exclude(site_id=site_id)
    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)
    return qs.first()


def find_titular_fixed_post_on_other_site(
    *,
    guard_id: int,
    site_id: int,
    shift_type: str,
) -> FixedPost | None:
    """Poste fixe actif où ce vigile est déjà titulaire sur un autre site."""
    return (
        FixedPost.objects.filter(
            titular_guard_id=guard_id,
            shift_type=shift_type,
            is_active=True,
        )
        .exclude(site_id=site_id)
        .select_related("site")
        .first()
    )


def conflict_error_message(conflict: ShiftAssignment) -> str:
    site_name = conflict.site.name if conflict.site_id else "un autre site"
    return (
        f"Ce vigile est déjà affecté sur le site « {site_name} » "
        f"le {conflict.shift_date.strftime('%d/%m/%Y')} "
        f"({conflict.start_time.strftime('%H:%M')} – {conflict.end_time.strftime('%H:%M')})."
    )


def titular_conflict_error_message(post: FixedPost) -> str:
    site_name = post.site.name if post.site_id else "un autre site"
    shift_label = post.get_shift_type_display()
    return f"Ce vigile est déjà titulaire du poste {shift_label} sur le site « {site_name} »."
