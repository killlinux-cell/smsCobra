"""Conversion d'un vigile titulaire en vigile roulement (et l'inverse)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from django.utils import timezone

from accounts.models import User
from accounts.roulement_username import generate_roulement_username, is_standard_roulement_username
from accounts.vigile_username_normalize import generate_vigile_username, is_standard_vigile_username
from shifts.roulement_cycle import default_cycle_anchor


@transaction.atomic
def convert_vigile_to_roulement(vigile: User, *, actor=None) -> User:
    if vigile.role != User.Role.VIGILE:
        raise ValidationError("Seuls les comptes vigiles peuvent être convertis en roulement.")
    if vigile.is_roulement and is_standard_roulement_username(vigile.username):
        raise ValidationError(f"{vigile.display_name} est déjà un vigile roulement.")

    from accounts.roulement_eligibility import vigile_is_active_titular

    if vigile_is_active_titular(vigile):
        raise ValidationError(
            "Ce vigile est titulaire sur un poste fixe. "
            "Seuls les vigiles non titulaires peuvent passer en roulement. "
            "Retirez-le d'abord via Affectations → Titulaires si besoin."
        )

    from webadmin.vigile_delete import release_vigile_from_active_posts

    release_vigile_from_active_posts(vigile, actor=actor)
    old_username = vigile.username
    vigile.username = generate_roulement_username()
    vigile.is_roulement = True
    if not vigile.roulement_cycle_anchor:
        vigile.roulement_cycle_anchor = default_cycle_anchor(timezone.localdate())
    vigile.save(update_fields=["username", "is_roulement", "roulement_cycle_anchor"])

    from reports.roulement_changes import log_vigile_converted_to_rlt

    log_vigile_converted_to_rlt(vigile=vigile, actor=actor)
    return vigile


def vigile_is_in_roulement_pool(vigile: User) -> bool:
    return bool(
        vigile
        and vigile.role == User.Role.VIGILE
        and (vigile.is_roulement or is_standard_roulement_username(vigile.username))
    )


@transaction.atomic
def convert_roulement_to_vigile(vigile: User, *, actor=None, cancel_future_missions: bool = True) -> User:
    """Retire un RLT du pool roulement pour pouvoir le titulariser (matricule VIR)."""
    if vigile.role != User.Role.VIGILE:
        raise ValidationError("Seuls les comptes vigiles peuvent quitter le roulement.")
    if not vigile_is_in_roulement_pool(vigile):
        raise ValidationError(f"{vigile.display_name} n'est pas un vigile roulement.")

    if cancel_future_missions:
        _cancel_future_roulement_missions(vigile, actor=actor)

    vigile.is_roulement = False
    vigile.roulement_cycle_anchor = None
    if is_standard_roulement_username(vigile.username) or not is_standard_vigile_username(vigile.username):
        vigile.username = generate_vigile_username()
    vigile.save(update_fields=["username", "is_roulement", "roulement_cycle_anchor"])

    from reports.roulement_changes import log_rlt_converted_to_vigile

    log_rlt_converted_to_vigile(vigile=vigile, actor=actor)
    return vigile


def _cancel_future_roulement_missions(vigile: User, *, actor=None) -> None:
    from checkins.models import Checkin
    from reports.roulement_changes import log_roulement_cancelled
    from shifts.models import ShiftAssignment
    from shifts.roulement_relief import restore_titular_after_roulement_cancel

    today = timezone.localdate()
    rows = list(
        ShiftAssignment.objects.filter(
            guard=vigile,
            status=ShiftAssignment.Status.ROULEMENT,
            shift_date__gte=today,
        ).select_related("guard", "site", "original_guard")
    )
    blocked = [a for a in rows if Checkin.objects.filter(assignment=a).exists()]
    if blocked:
        days = ", ".join(sorted({a.shift_date.strftime("%d/%m/%Y") for a in blocked}))
        raise ValidationError(
            f"Impossible de retirer {vigile.display_name} du roulement : "
            f"des pointages existent déjà sur une mission ({days}). "
            "Attendez la fin du service ou forcez la fin de service, puis réessayez."
        )
    for assignment in rows:
        log_roulement_cancelled(assignment=assignment, actor=actor)
        restore_titular_after_roulement_cancel(assignment)
        assignment.delete()
