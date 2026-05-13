from datetime import timedelta
from typing import Optional

from rest_framework import serializers

from checkins.models import Checkin
from .models import ShiftAssignment


class ShiftAssignmentSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    has_start = serializers.SerializerMethodField()
    has_end = serializers.SerializerMethodField()
    can_end = serializers.SerializerMethodField()
    end_block_reason = serializers.SerializerMethodField()
    last_start_at = serializers.SerializerMethodField()
    last_presence_at = serializers.SerializerMethodField()
    presence_due_at = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAssignment
        fields = "__all__"

    def _last_at(self, obj: ShiftAssignment, checkin_type: str):
        return (
            obj.checkins.filter(type=checkin_type).order_by("-timestamp").values_list("timestamp", flat=True).first()
        )

    def get_has_start(self, obj: ShiftAssignment) -> bool:
        return obj.checkins.filter(type=Checkin.Type.START).exists()

    def get_has_end(self, obj: ShiftAssignment) -> bool:
        return obj.checkins.filter(type=Checkin.Type.END).exists()

    def get_can_end(self, obj: ShiftAssignment) -> bool:
        # UI & sécurité: on évite les fins sans prise de service.
        if not obj.checkins.filter(type=Checkin.Type.START).exists():
            return False
        if obj.checkins.filter(type=Checkin.Type.END).exists():
            return False

        # Si le créneau a une relève (relais), on autorise la fin seulement après prise de service du relève.
        if not obj.relieved_by_id:
            return True
        incoming = obj.relieved_by
        return Checkin.objects.filter(assignment=incoming, type=Checkin.Type.START).exists()

    def get_end_block_reason(self, obj: ShiftAssignment) -> Optional[str]:
        if not obj.checkins.filter(type=Checkin.Type.START).exists():
            return "La prise de service doit être effectuée avant la fin de service."
        if obj.checkins.filter(type=Checkin.Type.END).exists():
            return "La fin de service a déjà été effectuée."
        if not obj.relieved_by_id:
            return None

        incoming = obj.relieved_by
        incoming_has_start = Checkin.objects.filter(assignment=incoming, type=Checkin.Type.START).exists()
        if not incoming_has_start:
            return (
                "Fin bloquée : le vigile de relève doit d'abord pointer la prise de service "
                f"(n°{incoming.id})."
            )
        return None

    def get_last_start_at(self, obj: ShiftAssignment):
        dt = self._last_at(obj, Checkin.Type.START)
        return dt.isoformat() if dt else None

    def get_last_presence_at(self, obj: ShiftAssignment):
        dt = self._last_at(obj, Checkin.Type.PRESENCE)
        return dt.isoformat() if dt else None

    def get_presence_due_at(self, obj: ShiftAssignment):
        """
        Prochaine fenêtre de confirmation présence (1h) basée sur la dernière présence,
        sinon basée sur la prise de service.
        """
        last_presence = self._last_at(obj, Checkin.Type.PRESENCE)
        if last_presence:
            return (last_presence + timedelta(hours=1)).isoformat()

        last_start = self._last_at(obj, Checkin.Type.START)
        if last_start:
            return (last_start + timedelta(hours=1)).isoformat()

        return None
