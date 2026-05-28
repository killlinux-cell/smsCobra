import logging
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import FixedPost, ShiftAssignment

_logger = logging.getLogger(__name__)


def _slot_for(shift_type: str):
    if shift_type == FixedPost.ShiftType.DAY:
        return time(6, 0), time(18, 0)
    return time(18, 0), time(6, 0)


def _in_fixed_post_range(post: FixedPost, day: date) -> bool:
    if post.start_date and day < post.start_date:
        return False
    if post.end_date and day > post.end_date:
        return False
    return True


@transaction.atomic
def ensure_assignments_for_dates(days: list[date]) -> None:
    if not days:
        return
    unique_days = sorted(set(days))
    posts = (
        FixedPost.objects.select_related("site", "titular_guard", "replacement_guard")
        .filter(is_active=True)
        .order_by("site_id", "shift_type")
    )
    for day in unique_days:
        for post in posts:
            if not _in_fixed_post_range(post, day):
                continue
            start_time, end_time = _slot_for(post.shift_type)
            guard = post.current_guard
            defaults = {
                "guard": guard,
                "end_time": end_time,
                "status": ShiftAssignment.Status.REPLACED
                if post.replacement_active and post.replacement_guard_id
                else ShiftAssignment.Status.SCHEDULED,
                "original_guard": post.titular_guard
                if post.replacement_active and post.replacement_guard_id
                else None,
            }
            # Ne modifie pas une affectation existante (historique / ajustements manuels).
            # Exclure les Extras (renforts temporaires) du lookup — ils coexistent avec le titulaire.
            existing = ShiftAssignment.objects.filter(
                site=post.site,
                shift_date=day,
                start_time=start_time,
                guard=guard,
            ).exclude(status=ShiftAssignment.Status.EXTRA).first()
            if not existing:
                ShiftAssignment.objects.create(
                    site=post.site,
                    shift_date=day,
                    start_time=start_time,
                    **defaults,
                )

    # (Re)lier la passation jour -> nuit par répartition (effectifs potentiellement différents).
    active_q = models.Q(status__in=ShiftAssignment.active_on_duty_statuses())
    for day in unique_days:
        next_day = day + timedelta(days=1)
        day_rows = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(
                active_q,
                shift_date=day,
                start_time=time(6, 0),
            )
            .order_by("site_id", "guard_id", "id")
        )
        night_rows_same_day = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(
                active_q,
                shift_date=day,
                start_time=time(18, 0),
            )
            .order_by("site_id", "guard_id", "id")
        )
        day_by_site: dict[int, list[ShiftAssignment]] = {}
        night_by_site: dict[int, list[ShiftAssignment]] = {}
        for row in day_rows:
            day_by_site.setdefault(row.site_id, []).append(row)
        for row in night_rows_same_day:
            night_by_site.setdefault(row.site_id, []).append(row)
        for site_id, outgoing_rows in day_by_site.items():
            incoming_rows = night_by_site.get(site_id, [])
            _link_relieved_by_distributed(outgoing_rows, incoming_rows)

        night_rows = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(
                active_q,
                shift_date=day,
                start_time=time(18, 0),
            )
            .order_by("site_id", "guard_id", "id")
        )
        day_rows_next = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(
                active_q,
                shift_date=next_day,
                start_time=time(6, 0),
            )
            .order_by("site_id", "guard_id", "id")
        )
        night_by_site = {}
        day_next_by_site: dict[int, list[ShiftAssignment]] = {}
        for row in night_rows:
            night_by_site.setdefault(row.site_id, []).append(row)
        for row in day_rows_next:
            day_next_by_site.setdefault(row.site_id, []).append(row)
        for site_id, outgoing_rows in night_by_site.items():
            incoming_rows = day_next_by_site.get(site_id, [])
            _link_relieved_by_distributed(outgoing_rows, incoming_rows)


def _link_relieved_by_distributed(
    outgoing_rows: list[ShiftAssignment],
    incoming_rows: list[ShiftAssignment],
) -> None:
    if not outgoing_rows:
        return
    if not incoming_rows:
        for row in outgoing_rows:
            _link_relieved_by(row, None)
        return
    # Répartition circulaire : gère les cas 5->2, 2->5, etc.
    for idx, row in enumerate(outgoing_rows):
        incoming = incoming_rows[idx % len(incoming_rows)]
        _link_relieved_by(row, incoming)


def _link_relieved_by(row: ShiftAssignment, incoming: ShiftAssignment | None) -> None:
    incoming_id = incoming.id if incoming else None
    if row.relieved_by_id == incoming_id:
        return
    row.relieved_by = incoming
    try:
        row.save(update_fields=["relieved_by"])
    except ValidationError:
        _logger.warning(
            "Passation non liee (affectation %s, relève %s) : validation refusee.",
            row.pk,
            incoming_id,
            exc_info=True,
        )
        row.refresh_from_db(fields=["relieved_by"])
