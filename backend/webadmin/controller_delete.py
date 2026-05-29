"""Vérifications et suppression d'un compte contrôleur."""

from __future__ import annotations

from accounts.models import ControllerSiteAssignment, ControllerVisit, User


def get_controller_delete_context(controller: User) -> dict:
    """Volumes de données liées (avertissement avant suppression)."""
    return {
        "blockers": [],
        "can_delete": True,
        "counts": {
            "site_assignments": ControllerSiteAssignment.objects.filter(
                controller=controller
            ).count(),
            "visits": ControllerVisit.objects.filter(controller=controller).count(),
        },
    }


def delete_controller(controller: User) -> None:
    controller.delete()
