"""Annulation des renforts Extra planifiés (sans pointage)."""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from checkins.models import Checkin
from shifts.models import ShiftAssignment


class ExtraCancelError(Exception):
    pass


def extra_reinforcement_queryset(
    *,
    site_id: int,
    guard_id: int,
    start_time,
    from_date: date | None = None,
):
    day = from_date or timezone.localdate()
    start_exists = Checkin.objects.filter(
        assignment_id=OuterRef("pk"),
        type=Checkin.Type.START,
    )
    return (
        ShiftAssignment.objects.filter(
            site_id=site_id,
            guard_id=guard_id,
            start_time=start_time,
            status=ShiftAssignment.Status.EXTRA,
            shift_date__gte=day,
        )
        .annotate(has_start=Exists(start_exists))
        .order_by("shift_date")
    )


@transaction.atomic
def cancel_extra_reinforcement(
    *,
    site_id: int,
    guard_id: int,
    start_time,
    from_date: date | None = None,
) -> dict:
    """
    Supprime les jours Extra restants sans prise de service.
    Les jours déjà pointés sont conservés.
    """
    rows = list(extra_reinforcement_queryset(
        site_id=site_id,
        guard_id=guard_id,
        start_time=start_time,
        from_date=from_date,
    ))
    if not rows:
        raise ExtraCancelError("Aucun renfort Extra à retirer pour ce vigile sur ce créneau.")

    deleted = 0
    skipped_in_service = 0
    for row in rows:
        if row.has_start:
            skipped_in_service += 1
            continue
        row.delete()
        deleted += 1

    if deleted == 0 and skipped_in_service > 0:
        raise ExtraCancelError(
            "Tous les jours restants ont déjà une prise de service : "
            "le renfort ne peut plus être retiré automatiquement."
        )

    return {
        "deleted": deleted,
        "skipped_in_service": skipped_in_service,
        "remaining": skipped_in_service,
    }
