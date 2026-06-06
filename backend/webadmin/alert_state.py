"""État des alertes critiques pour le tableau de bord (aujourd'hui, temps réel)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone

from accounts.models import User
from alerts.models import LateAlert
from checkins.models import Checkin
from shifts.models import ShiftAssignment

_logger = logging.getLogger(__name__)

_ALERT_SCAN_CACHE_KEY = "cobra:webadmin_alert_scan"
_ALERT_SCAN_INTERVAL_SEC = 180

_ADMIN_ROLES = {
    User.Role.SUPER_ADMIN,
    User.Role.ADMIN_SOCIETE,
    User.Role.SUPERVISEUR,
}


def user_can_see_admin_alerts(user) -> bool:
    return user.is_authenticated and getattr(user, "role", "") in _ADMIN_ROLES


def refresh_late_alerts_if_due() -> None:
    """Lance la détection retards / passation / présence (au plus toutes les 3 min)."""
    if not cache.add(_ALERT_SCAN_CACHE_KEY, 1, timeout=_ALERT_SCAN_INTERVAL_SEC):
        return
    try:
        from alerts.tasks import detect_missed_shift_task

        detect_missed_shift_task()
    except Exception:
        cache.delete(_ALERT_SCAN_CACHE_KEY)
        _logger.exception(
            "Echec du scan d'alertes depuis le tableau de bord (la page reste accessible)."
        )


def compute_replacement_needed(for_day: date | None = None) -> list[dict]:
    """Affectations du jour sans prise de service après la tolérance de retard."""
    filter_day = for_day or timezone.localdate()
    day_assignments = list(
        ShiftAssignment.objects.select_related("site", "guard", "original_guard")
        .filter(
            shift_date=filter_day,
            status__in=ShiftAssignment.active_on_duty_statuses(),
        )
        .order_by("site__name", "start_time")
    )
    if not day_assignments:
        return []
    started_assignment_ids = set(
        Checkin.objects.filter(
            assignment_id__in=[a.id for a in day_assignments],
            type=Checkin.Type.START,
        ).values_list("assignment_id", flat=True)
    )
    now = timezone.now()
    replacement_needed = []
    for assignment in day_assignments:
        if assignment.id in started_assignment_ids:
            continue
        tz = ZoneInfo(assignment.site.timezone or "UTC")
        deadline = datetime.combine(
            assignment.shift_date,
            assignment.start_time,
            tzinfo=tz,
        ) + timedelta(minutes=assignment.site.late_tolerance_minutes)
        if now <= deadline:
            continue
        minutes_overdue = int((now - deadline).total_seconds() // 60)
        replacement_needed.append(
            {
                "assignment": assignment,
                "deadline": deadline,
                "minutes_overdue": max(minutes_overdue, 0),
            }
        )
    return replacement_needed


def get_live_critical_alert_summary(for_day: date | None = None) -> dict:
    """Compteurs alertes ouvertes + remplacements à prévoir (jour courant par défaut)."""
    refresh_late_alerts_if_due()
    filter_day = for_day or timezone.localdate()
    open_count = LateAlert.objects.filter(
        triggered_at__date=filter_day,
        status=LateAlert.Status.OPEN,
    ).count()
    replacement_needed = compute_replacement_needed(filter_day)
    replacement_count = len(replacement_needed)
    return {
        "filter_day": filter_day,
        "alerts_open_count": open_count,
        "replacement_needed": replacement_needed,
        "replacement_needed_count": replacement_count,
        "critical_count": open_count + replacement_count,
    }
