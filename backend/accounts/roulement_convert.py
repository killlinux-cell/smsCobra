"""Conversion d'un vigile titulaire en vigile roulement."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from accounts.roulement_username import generate_roulement_username, is_standard_roulement_username


@transaction.atomic
def convert_vigile_to_roulement(vigile: User, *, actor=None) -> User:
    if vigile.role != User.Role.VIGILE:
        raise ValidationError("Seuls les comptes vigiles peuvent être convertis en roulement.")
    if vigile.is_roulement and is_standard_roulement_username(vigile.username):
        raise ValidationError(f"{vigile.display_name} est déjà un vigile roulement.")

    from webadmin.vigile_delete import release_vigile_from_active_posts

    release_vigile_from_active_posts(vigile, actor=actor)
    old_username = vigile.username
    vigile.username = generate_roulement_username()
    vigile.is_roulement = True
    vigile.save(update_fields=["username", "is_roulement"])
    return vigile
