from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from shifts.models import ShiftAssignment

from .models import LateAlert
from shifts.dispatch_candidates import candidate_availability

User = get_user_model()


class LateAlertSerializer(serializers.ModelSerializer):
    """Alerte avec libellés exploitables par l’app mobile admin."""

    site_name = serializers.CharField(source="assignment.site.name", read_only=True)
    guard_display = serializers.CharField(source="assignment.guard.display_name", read_only=True)
    assignment_id = serializers.IntegerField(source="assignment.id", read_only=True)
    admin_recipient_display = serializers.SerializerMethodField()

    class Meta:
        model = LateAlert
        fields = [
            "id",
            "assignment",
            "assignment_id",
            "site_name",
            "guard_display",
            "admin_recipient",
            "admin_recipient_display",
            "status",
            "message",
            "triggered_at",
            "acknowledged_at",
            "resolved_at",
        ]

    def get_admin_recipient_display(self, obj: LateAlert) -> str | None:
        if not obj.admin_recipient_id:
            return None
        u = obj.admin_recipient
        return (u.get_full_name() or "").strip() or u.username


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


class ReplacementNeededRowSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField(source="assignment.id")
    site_name = serializers.CharField(source="assignment.site.name")
    guard_display = serializers.CharField(source="assignment.guard.display_name")
    minutes_overdue = serializers.IntegerField()
    start_time = serializers.TimeField(source="assignment.start_time")
    end_time = serializers.TimeField(source="assignment.end_time")
    status = serializers.CharField(source="assignment.status")


class VigileBriefSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    face_enrollment_ok = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "profile_photo",
            "face_enrollment_ok",
        ]

    def get_display_name(self, obj: User) -> str:
        return obj.display_name

    def get_profile_photo(self, obj: User):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_face_enrollment_ok(self, obj: User) -> bool:
        return bool(obj.profile_photo and obj.face_embedding)


class DispatchCandidateSerializer(VigileBriefSerializer):
    dispatch_available = serializers.SerializerMethodField()
    busy_reason = serializers.SerializerMethodField()

    class Meta(VigileBriefSerializer.Meta):
        fields = VigileBriefSerializer.Meta.fields + [
            "dispatch_available",
            "busy_reason",
        ]

    def get_dispatch_available(self, obj: User) -> bool:
        assignment = self.context.get("dispatch_assignment")
        if assignment is None:
            busy_today = self.context.get("busy_today_ids") or set()
            return obj.pk not in busy_today
        available, _ = candidate_availability(assignment, obj)
        return available

    def get_busy_reason(self, obj: User) -> str:
        assignment = self.context.get("dispatch_assignment")
        if assignment is None:
            labels = self.context.get("busy_today_labels") or {}
            return labels.get(obj.pk, "")
        available, reason = candidate_availability(assignment, obj)
        return "" if available else reason
