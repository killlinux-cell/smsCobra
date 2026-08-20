"""Création d'affectations roulement (couverture manuelle, horaires du site cible)."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from shifts.guard_conflicts import conflict_error_message, find_assignment_conflict_on_other_site
from shifts.models import ShiftAssignment
from shifts.roulement_cycle import validate_service_days
from shifts.site_shift_times import SHIFT_DAY, SHIFT_NIGHT, slot_times_for_site
from sites.models import Site


def validate_roulement_guard(guard: User) -> None:
    if guard.role != User.Role.VIGILE:
        raise ValidationError("Seul un compte vigile peut être en roulement.")
    if not guard.is_roulement:
        raise ValidationError(
            f"{guard.display_name} n'est pas un vigile roulement (matricule RLT-). "
            "Créez-le ou convertissez-le depuis la section Roulement."
        )
    if not guard.is_active:
        raise ValidationError("Ce vigile roulement est inactif.")


def validate_create_roulement_assignment(
    *,
    guard: User,
    site: Site,
    shift_date: date,
    shift_type: str,
    roulement_days: int = 1,
) -> None:
    validate_roulement_guard(guard)
    if not site.is_active:
        raise ValidationError("Ce site est inactif.")
    if shift_type not in (SHIFT_DAY, SHIFT_NIGHT):
        raise ValidationError("Type de poste invalide (jour ou nuit).")
    required = site.staff_required_for_shift(shift_type)
    if required <= 0:
        raise ValidationError(
            f"Aucun poste {'jour' if shift_type == SHIFT_DAY else 'nuit'} "
            f"n'est configuré sur ce site."
        )
    days = max(1, min(int(roulement_days or 1), 31))
    validate_service_days(guard=guard, shift_date=shift_date, roulement_days=days)
    start_time, _ = slot_times_for_site(site, shift_type)
    for offset in range(days):
        day = shift_date + timedelta(days=offset)
        duplicate = ShiftAssignment.objects.filter(
            guard=guard,
            site=site,
            shift_date=day,
            start_time=start_time,
        ).exclude(status=ShiftAssignment.Status.EXTRA).first()
        if duplicate:
            raise ValidationError(
                f"Une affectation existe déjà pour {guard.username} sur « {site.name} » "
                f"le {day.strftime('%d/%m/%Y')} ({start_time.strftime('%H:%M')})."
            )
        conflict = find_assignment_conflict_on_other_site(
            guard_id=guard.pk,
            site_id=site.pk,
            shift_date=day,
            start_time=start_time,
        )
        if conflict and not guard.is_roulement:
            raise ValidationError(conflict_error_message(conflict))


@transaction.atomic
def create_roulement_assignments(
    *,
    guard: User,
    site: Site,
    shift_date: date,
    shift_type: str,
    roulement_days: int = 1,
) -> list[ShiftAssignment]:
    validate_create_roulement_assignment(
        guard=guard,
        site=site,
        shift_date=shift_date,
        shift_type=shift_type,
        roulement_days=roulement_days,
    )
    days = max(1, min(int(roulement_days or 1), 31))
    start_time, end_time = slot_times_for_site(site, shift_type)
    created: list[ShiftAssignment] = []
    for offset in range(days):
        day = shift_date + timedelta(days=offset)
        assignment = ShiftAssignment.objects.create(
            guard=guard,
            site=site,
            shift_date=day,
            start_time=start_time,
            end_time=end_time,
            status=ShiftAssignment.Status.ROULEMENT,
            relieved_by=None,
        )
        created.append(assignment)
    return created
