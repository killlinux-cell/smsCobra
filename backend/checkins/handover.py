"""Règles de passation entre vigiles (relève jour ↔ nuit)."""

from __future__ import annotations

from django.utils import timezone

from checkins.models import Checkin
from checkins.window import start_checkin_deadline
from shifts.models import ShiftAssignment


def incoming_relief_has_started(incoming: ShiftAssignment) -> bool:
    return Checkin.objects.filter(
        assignment=incoming,
        type=Checkin.Type.START,
    ).exists()


def incoming_relief_is_failed(incoming: ShiftAssignment, *, now=None) -> bool:
    """
    Relève considéré comme absent / manqué : le vigile sortant peut clôturer
    sans attendre indéfiniment (ex. 3 vigiles jour, un absent bloque la nuit).
    """
    if incoming_relief_has_started(incoming):
        return False
    if incoming.status == ShiftAssignment.Status.MISSED:
        return True
    ts = now if now is not None else timezone.now()
    deadline = start_checkin_deadline(
        incoming,
        tolerance_minutes=incoming.site.relief_late_alert_minutes,
    )
    return ts > deadline


def outgoing_end_blocked_by_incoming_relief(
    outgoing: ShiftAssignment,
    *,
    now=None,
) -> tuple[bool, str | None]:
    """
    Retourne (bloqué, message). Ne bloque pas si le relève est clairement absent.
    """
    if not outgoing.relieved_by_id:
        return False, None
    incoming = outgoing.relieved_by
    if incoming_relief_has_started(incoming):
        return False, None
    if incoming_relief_is_failed(incoming, now=now):
        return False, None
    return True, (
        "Fin bloquée : le vigile de relève doit d'abord pointer la prise de service "
        f"(n°{incoming.id})."
    )
