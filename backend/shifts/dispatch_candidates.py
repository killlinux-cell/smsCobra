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


def dispatch_busy_labels(assignment: ShiftAssignment) -> dict[int, str]:
    """Libellés « occupé » par vigile pour le créneau de l'affectation."""
    busy_ids = guard_ids_busy_on_slot(
        shift_date=assignment.shift_date,
        start_time=assignment.start_time,
        exclude_assignment_id=assignment.pk,
    )
    labels: dict[int, str] = {}
    for gid in busy_ids:
        if gid == assignment.guard_id:
            labels[gid] = "sur ce poste"
            continue
        conflict = find_assignment_conflict_on_other_site(
            guard_id=gid,
            site_id=assignment.site_id,
            shift_date=assignment.shift_date,
            start_time=assignment.start_time,
            exclude_assignment_id=assignment.pk,
        )
        if conflict:
            labels[gid] = f"occupé — {conflict.site.name}"
        else:
            labels[gid] = "occupé sur ce créneau"
    return labels


def dispatch_busy_today_labels(*, exclude_assignment_id: int | None = None) -> dict[int, str]:
    today = timezone.localdate()
    qs = (
        _active_assignment_qs()
        .filter(shift_date=today)
        .select_related("site")
    )
    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)
    labels: dict[int, str] = {}
    for row in qs.values("guard_id", "site__name", "start_time"):
        gid = row["guard_id"]
        site = row["site__name"] or "site"
        start = row["start_time"]
        start_s = start.strftime("%H:%M") if hasattr(start, "strftime") else str(start)
        labels[gid] = f"occupé — {site} ({start_s})"
    return labels


def replacement_candidate_queryset(
    assignment: ShiftAssignment,
    *,
    include_busy: bool = False,
) -> QuerySet[User]:
    """
    Vigiles proposés pour remplacer sur une affectation.
    Par défaut : libres sur le créneau. Si include_busy : tous sauf le vigile du poste.
    """
    qs = _base_eligible_vigiles_qs().exclude(pk=assignment.guard_id)
    if include_busy:
        return qs
    busy = guard_ids_busy_on_slot(
        shift_date=assignment.shift_date,
        start_time=assignment.start_time,
        exclude_assignment_id=assignment.pk,
    )
    return qs.exclude(pk__in=busy)


def vigiles_free_today_queryset(
    *,
    exclude_assignment_id: int | None = None,
    include_busy: bool = False,
) -> QuerySet[User]:
    """Vigiles sans garde active aujourd'hui (ou tous si include_busy)."""
    if include_busy:
        return _base_eligible_vigiles_qs()
    busy = guard_ids_busy_today(exclude_assignment_id=exclude_assignment_id)
    return _base_eligible_vigiles_qs().exclude(pk__in=busy)


def candidate_availability(
    assignment: ShiftAssignment,
    guard: User,
) -> tuple[bool, str]:
    """Retourne (disponible, motif si occupé)."""
    ok, reason = is_guard_eligible_for_dispatch(assignment, guard)
    if ok:
        return True, ""
    if guard.pk == assignment.guard_id:
        return False, "sur ce poste"
    if "Déjà en service" in reason or "occupé" in reason.lower():
        return False, reason.replace("Déjà en service sur ", "occupé — ")
    return False, reason


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
