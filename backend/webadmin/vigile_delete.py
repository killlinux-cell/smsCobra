"""Vérifications et suppression d'un compte vigile."""

from __future__ import annotations

from django.db.models import Q

from accounts.models import User
from checkins.models import Checkin
from reports.models import AttendanceReport
from shifts.models import FixedPost, ShiftAssignment


def get_vigile_delete_context(vigile: User) -> dict:
    """Bloqueurs éventuels + volumes de données liées (avertissement)."""
    blockers: list[str] = []

    for fp in (
        FixedPost.objects.filter(is_active=True, titular_guard=vigile)
        .select_related("site")
    ):
        site_name = fp.site.name if fp.site_id else "Site"
        blockers.append(
            f"Titulaire en poste sur « {site_name} » ({fp.get_shift_type_display()}). "
            f"Réassignez le poste fixe avant suppression."
        )

    for fp in (
        FixedPost.objects.filter(
            is_active=True,
            replacement_guard=vigile,
            replacement_active=True,
        ).select_related("site")
    ):
        site_name = fp.site.name if fp.site_id else "Site"
        blockers.append(
            f"Remplaçant actif sur « {site_name} » ({fp.get_shift_type_display()}). "
            f"Désactivez le remplaçant ou changez le titulaire."
        )

    assignment_q = Q(guard=vigile) | Q(original_guard=vigile)
    return {
        "blockers": blockers,
        "can_delete": not blockers,
        "counts": {
            "assignments": ShiftAssignment.objects.filter(assignment_q).count(),
            "checkins": Checkin.objects.filter(guard=vigile).count(),
            "reports": AttendanceReport.objects.filter(guard=vigile).count(),
            "fixed_posts_titular": FixedPost.objects.filter(
                titular_guard=vigile
            ).count(),
        },
    }


def delete_vigile(vigile: User) -> None:
    ctx = get_vigile_delete_context(vigile)
    if not ctx["can_delete"]:
        raise ValueError(ctx["blockers"][0])
    vigile.delete()
