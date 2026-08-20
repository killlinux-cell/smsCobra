"""Vigiles éligibles au roulement (non titulaires sur un poste fixe actif)."""

from __future__ import annotations

from accounts.models import User
from shifts.models import FixedPost


def active_titular_guard_ids() -> set[int]:
    return set(
        FixedPost.objects.filter(is_active=True, titular_guard_id__isnull=False).values_list(
            "titular_guard_id", flat=True
        )
    )


def non_titular_vigile_queryset():
    """Vigiles VIR actifs qui ne sont titulaires sur aucun poste fixe."""
    titular_ids = active_titular_guard_ids()
    return (
        User.objects.filter(role=User.Role.VIGILE, is_roulement=False, is_active=True)
        .exclude(pk__in=titular_ids)
        .order_by("first_name", "last_name", "username")
    )


def vigile_is_active_titular(vigile: User) -> bool:
    if not vigile.pk:
        return False
    return FixedPost.objects.filter(is_active=True, titular_guard_id=vigile.pk).exists()
