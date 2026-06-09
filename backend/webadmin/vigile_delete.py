"""Vérifications et suppression d'un compte vigile."""

from __future__ import annotations

from django.db.models import Q

from accounts.models import User
from checkins.models import Checkin
from reports.models import AttendanceReport
from shifts.models import FixedPost, ShiftAssignment


def release_vigile_from_active_posts(vigile: User, *, actor=None) -> int:
    """
    Détache le vigile de tous les postes fixes actifs (titulaire, suspendu ou remplaçant).
    Permet la suppression ou la mutation sans blocage manuel.
    """
    from shifts.titular_replacement import dismiss_suspended_titular, retire_titular_fixed_post

    released = 0
    reason = f"Libération automatique du compte vigile {vigile.display_name}."
    posts = list(
        FixedPost.objects.filter(is_active=True)
        .filter(
            Q(titular_guard=vigile)
            | Q(suspended_titular_guard=vigile)
            | Q(replacement_guard=vigile, replacement_active=True)
        )
        .select_related("site", "titular_guard")
    )
    for fp in posts:
        if fp.titular_guard_id == vigile.id:
            retire_titular_fixed_post(
                fp,
                reason=reason,
                actor=actor,
                clear_suspended=True,
            )
            released += 1
            continue
        if fp.suspended_titular_guard_id == vigile.id:
            dismiss_suspended_titular(fp, reason=reason, actor=actor)
            released += 1
            continue
        if fp.replacement_guard_id == vigile.id and fp.replacement_active:
            fp.replacement_guard_id = None
            fp.replacement_active = False
            fp.save(update_fields=["replacement_guard_id", "replacement_active", "updated_at"])
            released += 1
    return released


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
            f"Utilisez « Libérer les postes puis supprimer » ou retirez le titulaire manuellement."
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
            f"Utilisez « Libérer les postes puis supprimer »."
        )

    for fp in (
        FixedPost.objects.filter(
            is_active=True,
            suspended_titular_guard=vigile,
        ).select_related("site")
    ):
        site_name = fp.site.name if fp.site_id else "Site"
        blockers.append(
            f"Titulaire suspendu sur « {site_name} » ({fp.get_shift_type_display()}). "
            f"Réintégrez-le, libérez-le ou utilisez « Libérer les postes puis supprimer »."
        )

    assignment_q = Q(guard=vigile) | Q(original_guard=vigile)
    return {
        "blockers": blockers,
        "can_delete": not blockers,
        "can_force_release": bool(blockers),
        "counts": {
            "assignments": ShiftAssignment.objects.filter(assignment_q).count(),
            "checkins": Checkin.objects.filter(guard=vigile).count(),
            "reports": AttendanceReport.objects.filter(guard=vigile).count(),
            "fixed_posts_titular": FixedPost.objects.filter(
                titular_guard=vigile
            ).count(),
            "active_posts": FixedPost.objects.filter(is_active=True)
            .filter(
                Q(titular_guard=vigile)
                | Q(suspended_titular_guard=vigile)
                | Q(replacement_guard=vigile, replacement_active=True)
            )
            .count(),
        },
    }


def delete_vigile(vigile: User, *, actor=None, force_release: bool = False) -> None:
    if force_release:
        release_vigile_from_active_posts(vigile, actor=actor)
    ctx = get_vigile_delete_context(vigile)
    if not ctx["can_delete"]:
        raise ValueError(ctx["blockers"][0])
    vigile.delete()
