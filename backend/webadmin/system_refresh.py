"""Purge des caches et resynchronisation planning / alertes (bouton Actualiser)."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

from shifts.services import ensure_assignments_for_horizon
from shifts.slot_occupancy import purge_all_sites_orphaned_scheduled
from sites.models import Site

_logger = logging.getLogger(__name__)

_ENSURE_PREFIX = "cobra:ensure_assignments"


def clear_operational_caches(*, for_day: date | None = None) -> None:
    """Vide les caches dashboard (alertes, postes ouverts, throttle planning)."""
    from webadmin.alert_state import invalidate_alert_summary_cache

    day = for_day or timezone.localdate()
    invalidate_alert_summary_cache(day)
    cache.delete("cobra:webadmin_stale_open_count")
    cache.delete("cobra:webadmin_alert_scan")
    for offset in range(0, 3):
        d = (day - timedelta(days=offset)).isoformat()
        for horizon in (31, 7, 1):
            cache.delete(f"{_ENSURE_PREFIX}:{d}:{horizon}")


def refresh_site_planning(*, site_id: int, from_date: date | None = None) -> int:
    """Nettoie les planifications orphelines d'un site puis régénère l'horizon."""
    day = from_date or timezone.localdate()
    from shifts.slot_occupancy import purge_orphaned_scheduled_for_slot
    from shifts.models import FixedPost

    purged = 0
    for shift_type in (FixedPost.ShiftType.DAY, FixedPost.ShiftType.NIGHT):
        purged += purge_orphaned_scheduled_for_slot(
            site_id=site_id,
            shift_type=shift_type,
            from_date=day,
        )
    ensure_assignments_for_horizon(from_day=day, days_ahead=31, force=True)
    clear_operational_caches(for_day=day)
    return purged


def refresh_operational_state(*, days_ahead: int = 31) -> dict:
    """
    Resynchronisation complète : caches, affectations orphelines, horizon titulaires.
    Déclenché par le bouton « Actualiser » du dashboard.
    """
    today = timezone.localdate()
    clear_operational_caches(for_day=today)
    purged = purge_all_sites_orphaned_scheduled(from_date=today)
    ensure_assignments_for_horizon(from_day=today, days_ahead=days_ahead, force=True)

    alerts_queued = False
    try:
        from alerts.tasks import detect_missed_shift_task

        detect_missed_shift_task.delay()
        alerts_queued = True
    except Exception:
        _logger.debug("Scan alertes non dispatché lors de l'actualisation.", exc_info=True)

    return {
        "purged_assignments": purged,
        "sites_count": Site.objects.filter(is_active=True).count(),
        "alerts_scan_queued": alerts_queued,
    }
