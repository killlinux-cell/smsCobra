import logging
from collections import defaultdict
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction

from shifts.site_shift_times import shift_type_for_start_time, slot_times_for_site

from .models import FixedPost, ShiftAssignment

_logger = logging.getLogger(__name__)


def _slot_for(post: FixedPost):
    return slot_times_for_site(post.site, post.shift_type)


def _in_fixed_post_range(post: FixedPost, day: date) -> bool:
    if post.start_date and day < post.start_date:
        return False
    if post.end_date and day > post.end_date:
        return False
    return True


def _purge_assignments_before_start(post: FixedPost) -> int:
    """Supprime les affectations planifiées avant la date de début du poste fixe."""
    if not post.start_date:
        return 0
    start_time, _ = _slot_for(post)
    guard_id = post.current_guard.id
    return (
        ShiftAssignment.objects.filter(
            site_id=post.site_id,
            start_time=start_time,
            guard_id=guard_id,
            shift_date__lt=post.start_date,
            status__in=ShiftAssignment.active_on_duty_statuses(),
        )
        .exclude(status=ShiftAssignment.Status.EXTRA)
        .delete()[0]
    )


_logger = logging.getLogger(__name__)

_ENSURE_ASSIGNMENTS_CACHE_PREFIX = "cobra:ensure_assignments"
_ENSURE_ASSIGNMENTS_INTERVAL_SEC = 300


def ensure_assignments_for_horizon(
    *,
    from_day: date | None = None,
    days_ahead: int = 31,
    force: bool = False,
) -> None:
    """
    Génère les affectations titulaires sur l'horizon demandé.
    Sur les pages web (GET), limité à une exécution toutes les 5 min pour éviter
    de ralentir chaque navigation.
    """
    from django.core.cache import cache
    from django.utils import timezone

    today = from_day or timezone.localdate()
    horizon = [today + timedelta(days=i) for i in range(max(1, days_ahead))]
    if force:
        ensure_assignments_for_dates(horizon)
        return
    cache_key = f"{_ENSURE_ASSIGNMENTS_CACHE_PREFIX}:{today.isoformat()}:{days_ahead}"
    if cache.add(cache_key, 1, timeout=_ENSURE_ASSIGNMENTS_INTERVAL_SEC):
        ensure_assignments_for_dates(horizon)


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
    for post in posts:
        _purge_assignments_before_start(post)

    for day in unique_days:
        for post in posts:
            if not _in_fixed_post_range(post, day):
                continue
            start_time, end_time = _slot_for(post)
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

    # (Re)lier la passation jour -> nuit par répartition (horaires propres à chaque site).
    active_q = models.Q(status__in=ShiftAssignment.active_on_duty_statuses())
    for day in unique_days:
        next_day = day + timedelta(days=1)
        rows_today = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(active_q, shift_date=day)
            .order_by("site_id", "guard_id", "id")
        )
        day_by_site: dict[int, list[ShiftAssignment]] = defaultdict(list)
        night_by_site: dict[int, list[ShiftAssignment]] = defaultdict(list)
        for row in rows_today:
            st = shift_type_for_start_time(row.site, row.start_time)
            if st == FixedPost.ShiftType.DAY:
                day_by_site[row.site_id].append(row)
            elif st == FixedPost.ShiftType.NIGHT:
                night_by_site[row.site_id].append(row)
        for site_id, outgoing_rows in day_by_site.items():
            incoming_rows = night_by_site.get(site_id, [])
            _link_relieved_by_distributed(outgoing_rows, incoming_rows)

        rows_next = list(
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(active_q, shift_date=next_day)
            .order_by("site_id", "guard_id", "id")
        )
        day_next_by_site: dict[int, list[ShiftAssignment]] = defaultdict(list)
        for row in rows_next:
            if shift_type_for_start_time(row.site, row.start_time) == FixedPost.ShiftType.DAY:
                day_next_by_site[row.site_id].append(row)
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
