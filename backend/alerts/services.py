import logging
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from shifts.models import ShiftAssignment

from .firebase_init import is_firebase_initialized
from .models import LateAlert

logger = logging.getLogger(__name__)
User = get_user_model()


def _fcm_data_payload(data: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """FCM exige des valeurs string dans le champ data."""
    if not data:
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if v is None:
            continue
        out[str(k)] = v if isinstance(v, str) else str(v)
    return out


def send_push_to_admins(title: str, body: str, data: dict | None = None) -> int:
    if not is_firebase_initialized():
        logger.debug("Push FCM ignoré : Firebase Admin non initialisé.")
        return 0

    from firebase_admin import messaging

    admins = User.objects.filter(role__in=["super_admin", "admin_societe", "superviseur"]).exclude(
        fcm_token=""
    )
    payload = _fcm_data_payload(data)
    sent = 0
    for admin in admins:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=admin.fcm_token,
                data=payload,
            )
            messaging.send(message)
            sent += 1
        except Exception as exc:  # pragma: no cover
            logger.warning("Push FCM failed for user=%s error=%s", admin.id, exc)
    return sent


def _base_data(assignment: ShiftAssignment, extra: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    data: Dict[str, Any] = {
        "assignment_id": str(assignment.id),
        "site": assignment.site.name,
    }
    if extra:
        data.update(extra)
    return _fcm_data_payload(data)


def notify_pointage_start(assignment: ShiftAssignment) -> int:
    """Push : vigile a pointé la prise de service."""
    g = assignment.guard
    s = assignment.site
    body = f"{g.display_name} @ {s.name} — début prévu {assignment.start_time.strftime('%H:%M')}"
    return send_push_to_admins(
        "SMS · Prise de service",
        body,
        _base_data(assignment, {"type": "pointage_start"}),
    )


def notify_pointage_end(assignment: ShiftAssignment) -> int:
    """Push : vigile a pointé la fin de service."""
    g = assignment.guard
    s = assignment.site
    body = f"{g.display_name} @ {s.name} — fin prévue {assignment.end_time.strftime('%H:%M')}"
    return send_push_to_admins(
        "SMS · Fin de service",
        body,
        _base_data(assignment, {"type": "pointage_end"}),
    )


def notify_dispatch_replacement(
    assignment: ShiftAssignment,
    previous_guard_name: str,
) -> int:
    """Push : remplacement de vigile sur un poste (web ou API)."""
    g = assignment.guard
    s = assignment.site
    body = f"{g.display_name} affecté sur {s.name} (remplace {previous_guard_name}). Poste n°{assignment.id}."
    return send_push_to_admins(
        "SMS · Dépêche / remplacement",
        body,
        _base_data(assignment, {"type": "dispatch", "previous_guard": previous_guard_name}),
    )


def resolve_retard_alerts_for_assignment(assignment: ShiftAssignment) -> int:
    """Quand la prise de service est enregistrée, clôturer l’alerte « retard » correspondante."""
    return LateAlert.objects.filter(
        assignment=assignment,
        status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
        message__startswith="Retard prise de service :",
    ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())


def resolve_passation_alerts_for_assignment(assignment: ShiftAssignment) -> int:
    """Quand le relève pointe le début, clôturer l’alerte passation sur cette affectation."""
    return LateAlert.objects.filter(
        assignment=assignment,
        status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
        message__startswith="Passation:",
    ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())


def resolve_fin_sans_pointage_alerts(assignment: ShiftAssignment) -> int:
    """Quand la fin est pointée, clôturer l’alerte « fin non enregistrée »."""
    return LateAlert.objects.filter(
        assignment=assignment,
        status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
        message__startswith="FinSansPointage:",
    ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())
