"""Serializers API admin — affectations / planning."""

from rest_framework import serializers

from accounts.models import User
from shifts.admin_assignment import (
    MODE_EXTRA,
    MODE_PLANIFIER,
    SHIFT_DAY,
    SHIFT_NIGHT,
    create_assignment,
    update_assignment,
)
from shifts.models import ShiftAssignment
from sites.models import Site


class AdminShiftAssignmentSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    guard_display = serializers.CharField(source="guard.display_name", read_only=True)
    original_guard_display = serializers.SerializerMethodField()
    shift_type = serializers.SerializerMethodField()

    class Meta:
        model = ShiftAssignment
        fields = [
            "id",
            "guard",
            "guard_display",
            "original_guard",
            "original_guard_display",
            "site",
            "site_name",
            "shift_date",
            "start_time",
            "end_time",
            "status",
            "shift_type",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_original_guard_display(self, obj: ShiftAssignment) -> str | None:
        if not obj.original_guard_id:
            return None
        return obj.original_guard.display_name

    def get_shift_type(self, obj: ShiftAssignment) -> str:
        from shifts.site_shift_times import shift_type_for_start_time

        st = shift_type_for_start_time(obj.site, obj.start_time)
        if st == "night":
            return SHIFT_NIGHT
        return SHIFT_DAY


class AdminShiftAssignmentCreateSerializer(serializers.Serializer):
    planning_mode = serializers.ChoiceField(
        choices=[(MODE_PLANIFIER, "Planifier"), (MODE_EXTRA, "Extra")],
        default=MODE_PLANIFIER,
    )
    extra_days = serializers.IntegerField(required=False, min_value=1, max_value=31, default=5)
    create_fixed_post = serializers.BooleanField(required=False, default=True)
    guard = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.VIGILE))
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.filter(is_active=True))
    shift_date = serializers.DateField()
    shift_type = serializers.ChoiceField(choices=[(SHIFT_DAY, "Jour"), (SHIFT_NIGHT, "Nuit")])

    def create(self, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError

        try:
            result = create_assignment(
                guard=validated_data["guard"],
                site=validated_data["site"],
                shift_date=validated_data["shift_date"],
                shift_type=validated_data["shift_type"],
                planning_mode=validated_data.get("planning_mode", MODE_PLANIFIER),
                extra_days=validated_data.get("extra_days") or 5,
                create_fixed_post=validated_data.get("create_fixed_post", True),
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise DRFValidationError(exc.message_dict) from exc
            raise DRFValidationError(list(exc.messages)) from exc
        if isinstance(result, list):
            return result[0]
        return result


class AdminShiftAssignmentUpdateSerializer(serializers.Serializer):
    guard = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.VIGILE))
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.filter(is_active=True))
    shift_date = serializers.DateField()
    shift_type = serializers.ChoiceField(choices=[(SHIFT_DAY, "Jour"), (SHIFT_NIGHT, "Nuit")])

    def update(self, instance, validated_data):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError

        try:
            return update_assignment(
                instance,
                guard=validated_data["guard"],
                site=validated_data["site"],
                shift_date=validated_data["shift_date"],
                shift_type=validated_data["shift_type"],
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise DRFValidationError(exc.message_dict) from exc
            raise DRFValidationError(list(exc.messages)) from exc
