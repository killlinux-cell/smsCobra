"""Appel commun après une dépêche : promotion titulaire si applicable."""

from __future__ import annotations

from django.core.exceptions import ValidationError

from shifts.models import FixedPost, ShiftAssignment
from shifts.titular_replacement import promote_replacement_to_titular_on_dispatch


def process_dispatch_replacement(
    assignment: ShiftAssignment,
    *,
    absent_guard_id: int,
    replacement_guard_id: int,
    actor=None,
) -> FixedPost | None:
    return promote_replacement_to_titular_on_dispatch(
        assignment,
        absent_guard_id=absent_guard_id,
        replacement_guard_id=replacement_guard_id,
        actor=actor,
    )


def dispatch_replacement_message(
    assignment: ShiftAssignment,
    *,
    previous_name: str,
    replacement_name: str,
    promoted_post: FixedPost | None,
) -> str:
    base = (
        f"Dépêche enregistrée : {replacement_name} est en poste "
        f"(titulaire d'origine sur l'affectation : {previous_name})."
    )
    if promoted_post is None:
        return base
    shift = promoted_post.get_shift_type_display()
    site = promoted_post.site.name if promoted_post.site_id else "site"
    return (
        f"{base} {replacement_name} est désormais **titulaire** sur « {site} » "
        f"({shift}). {previous_name} est suspendu jusqu'à réintégration par le superviseur "
        f"(Titulaires par site)."
    )
