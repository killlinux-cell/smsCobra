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
            ).exclude(status=ShiftAssignment.Status.EXTRA).first()
            if not existing:
                ShiftAssignment.objects.create(
                    site=post.site,
                    shift_date=day,
                    start_time=start_time,
                    **defaults,
                )

    # (Re)lier la passation jour -> nuit du même site (exclure les extras).
    _non_extra = ~models.Q(status=ShiftAssignment.Status.EXTRA)
    for day in unique_days:
        next_day = day + timedelta(days=1)
        day_rows = ShiftAssignment.objects.select_related("site").filter(
            _non_extra,
            shift_date=day,
            start_time=time(6, 0),
        )
        for row in day_rows:
            incoming = ShiftAssignment.objects.filter(
                _non_extra,
                site=row.site,
                shift_date=day,
                start_time=time(18, 0),
            ).first()
            _link_relieved_by(row, incoming)

        night_rows = ShiftAssignment.objects.select_related("site").filter(
            _non_extra,
            shift_date=day,
            start_time=time(18, 0),
        )
        for row in night_rows:
            incoming = ShiftAssignment.objects.filter(
                _non_extra,
                site=row.site,
                shift_date=next_day,
                start_time=time(6, 0),
            ).first()
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
