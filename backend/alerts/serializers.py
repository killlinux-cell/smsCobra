from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from shifts.models import ShiftAssignment

from .models import LateAlert

User = get_user_model()


class LateAlertSerializer(serializers.ModelSerializer):
    """Alerte avec libellés exploitables par l’app mobile admin."""

    site_name = serializers.CharField(source="assignment.site.name", read_only=True)
    guard_display = serializers.CharField(source="assignment.guard.display_name", read_only=True)
    assignment_id = serializers.IntegerField(source="assignment.id", read_only=True)

    class Meta:
        model = LateAlert
        fields = [
            "id",
            "assignment",
            "assignment_id",
            "site_name",
            "guard_display",
            "admin_recipient",
            "status",
            "message",
            "triggered_at",
            "acknowledged_at",
            "resolved_at",
        ]


class ShiftAssignmentDispatchSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    guard_display = serializers.CharField(source="guard.display_name", read_only=True)
    original_guard_display = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "site_name",
            "guard_display",
            "original_guard",
            "original_guard_display",
            "shift_date",
            "start_time",
            "end_time",
            "status",
        ]

    def get_original_guard_display(self, obj: ShiftAssignment) -> Optional[str]:
        if not obj.original_guard_id:
            return None
        return obj.original_guard.display_name


class VigileBriefSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "display_name"]

    def get_display_name(self, obj: User) -> str:
        return obj.display_name
