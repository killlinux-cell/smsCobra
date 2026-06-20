from webadmin.alert_state import get_live_critical_alert_summary, user_can_see_admin_alerts
from webadmin.open_shifts import count_stale_open_shifts


def cobra_critical_alerts(request):
    """Alertes critiques visibles sur toutes les pages du dashboard admin."""
    path = getattr(request, "path", "") or ""
    if not path.startswith("/dashboard/") or path.startswith("/dashboard/login"):
        return {}
    user = getattr(request, "user", None)
    if not user_can_see_admin_alerts(user):
        return {}
    summary = get_live_critical_alert_summary()
    stale_open = count_stale_open_shifts()
    return {
        "cobra_alerts_open_count": summary["alerts_open_count"],
        "cobra_replacement_needed_count": summary["replacement_needed_count"],
        "cobra_critical_count": summary["critical_count"],
        "cobra_stale_open_shifts_count": stale_open,
    }
