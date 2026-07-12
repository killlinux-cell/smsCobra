"""Clôture automatique des postes ouverts obsolètes lors d'un nouveau pointage."""

from __future__ import annotations

import logging

from django.db.models import Exists, OuterRef

from checkins.models import Checkin
from shifts.models import ShiftAssignment

logger = logging.getLogger(__name__)


def stale_open_assignments_for_guard(
    guard_id: int,
    *,
    before_shift_date,
    exclude_assignment_id: int | None = None,
):
    """Affectations antérieures avec prise mais sans fin."""
    start_exists = Checkin.objects.filter(
        assignment_id=OuterRef("pk"),
        type=Checkin.Type.START,
    )
    end_exists = Checkin.objects.filter(
        assignment_id=OuterRef("pk"),
        type=Checkin.Type.END,
    )
    qs = (
        ShiftAssignment.objects.filter(
            guard_id=guard_id,
            shift_date__lt=before_shift_date,
        )
        .filter(Exists(start_exists))
        .exclude(Exists(end_exists))
        .select_related("site", "guard")
        .order_by("shift_date", "start_time")
    )
    if exclude_assignment_id:
        qs = qs.exclude(pk=exclude_assignment_id)
    return qs


def auto_close_stale_open_assignments_before_start(
    guard_id: int,
    new_assignment: ShiftAssignment,
    *,
    actor=None,
) -> list[int]:
    """
    Quand un vigile démarre un service sur une date plus récente, clôturer
    automatiquement ses postes ouverts des jours précédents (ex. jour sans fin,
    binôme de nuit en place, reprise le lendemain).
    """
    from webadmin.admin_force_end import ForceEndError, supervisor_force_end_assignment

    closed_ids: list[int] = []
    for assignment in stale_open_assignments_for_guard(
        guard_id,
        before_shift_date=new_assignment.shift_date,
        exclude_assignment_id=new_assignment.pk,
    ):
        try:
            supervisor_force_end_assignment(
                assignment,
                actor=actor,
                reason=(
                    "Clôture automatique : nouveau service démarré "
                    f"(affectation n°{new_assignment.pk})."
                ),
                source_label="auto-prise",
            )
            closed_ids.append(assignment.pk)
        except ForceEndError as exc:
            logger.warning(
                "Clôture auto poste ouvert #%s ignorée : %s",
                assignment.pk,
                exc,
            )
    return closed_ids
