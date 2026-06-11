"""Vigiles éligibles pour un dépêchement (remplacement)."""

from __future__ import annotations

from datetime import date, time

from django.db.models import QuerySet
from django.utils import timezone

from accounts.models import User
from shifts.guard_conflicts import find_assignment_conflict_on_other_site
from shifts.models import ShiftAssignment


def _active_assignment_qs():
    return ShiftAssignment.objects.filter(
        status__in=ShiftAssignment.active_on_duty_statuses(),
    )


def guard_ids_busy_on_slot(
    *,
    shift_date: date,
    start_time: time,
    exclude_assignment_id: int | None = None,
) -> set[int]:
    """Vigiles déjà en service actif sur ce créneau (tous sites)."""
    qs = _active_assignment_qs().filter(
        shift_date=shift_date,
        start_time=start_time,
    )
    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)
    return set(qs.values_list("guard_id", flat=True))


def guard_ids_busy_today(*, exclude_assignment_id: int | None = None) -> set[int]:
    today = timezone.localdate()
    qs = _active_assignment_qs().filter(shift_date=today)
    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)
    return set(qs.values_list("guard_id", flat=True))


def _base_eligible_vigiles_qs() -> QuerySet[User]:
    return (
        User.objects.filter(role=User.Role.VIGILE, is_active=True)
        .exclude(profile_photo="")
        .exclude(face_embedding__isnull=True)
        .order_by("username")
    )


def replacement_candidate_queryset(
    assignment: ShiftAssignment,
) -> QuerySet[User]:
    """
    Vigiles disponibles pour remplacer sur une affectation :
    - actifs, empreinte faciale OK (peuvent pointer)
    - pas le vigile déjà sur le poste
    - pas déjà en service sur le même créneau (tout site)
    """
    busy = guard_ids_busy_on_slot(
        shift_date=assignment.shift_date,
        start_time=assignment.start_time,
        exclude_assignment_id=assignment.pk,
    )
    busy.add(assignment.guard_id)
    return _base_eligible_vigiles_qs().exclude(pk__in=busy)


def vigiles_free_today_queryset(
    *,
    exclude_assignment_id: int | None = None,
) -> QuerySet[User]:
    """Vigiles sans garde active aujourd'hui (liste par défaut avant choix du poste)."""
    busy = guard_ids_busy_today(exclude_assignment_id=exclude_assignment_id)
    return _base_eligible_vigiles_qs().exclude(pk__in=busy)


def is_guard_eligible_for_dispatch(
    assignment: ShiftAssignment,
    guard: User,
) -> tuple[bool, str]:
    """Contrôle unitaire (tests / validation)."""
    if guard.role != User.Role.VIGILE or not guard.is_active:
        return False, "Vigile inactif ou invalide."
    if guard.pk == assignment.guard_id:
        return False, "Déjà affecté à ce poste."
    if not guard.profile_photo or not guard.face_embedding:
        return False, "Photo ou empreinte faciale manquante."
    busy = guard_ids_busy_on_slot(
        shift_date=assignment.shift_date,
        start_time=assignment.start_time,
        exclude_assignment_id=assignment.pk,
    )
    if guard.pk in busy:
        conflict = find_assignment_conflict_on_other_site(
            guard_id=guard.pk,
            site_id=assignment.site_id,
            shift_date=assignment.shift_date,
            start_time=assignment.start_time,
            exclude_assignment_id=assignment.pk,
        )
        if conflict:
            return False, f"Déjà en service sur {conflict.site.name}."
        return False, "Déjà en service sur ce créneau."
    return True, ""
