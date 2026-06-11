from datetime import datetime, time

from django.utils import timezone
from rest_framework import serializers

from .models import Site


class SiteSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateField(
        required=False,
        write_only=True,
        help_text="Date d'ouverture du site (aligné webadmin).",
    )

    class Meta:
        model = Site
        fields = "__all__"

    def validate(self, attrs):
        late = attrs.get("late_tolerance_minutes")
        if late is not None:
            attrs["relief_late_alert_minutes"] = late
        instance = getattr(self, "instance", None)
        lat = attrs["latitude"] if "latitude" in attrs else (
            instance.latitude if instance else None
        )
        lon = attrs["longitude"] if "longitude" in attrs else (
            instance.longitude if instance else None
        )
        if (lat is None) != (lon is None):
            raise serializers.ValidationError(
                "Renseignez la latitude et la longitude ensemble, ou laissez les deux vides."
            )
        return attrs

    def validate_site_manager_phone(self, value):
        phone = (value or "").strip()
        if not phone:
            raise serializers.ValidationError(
                "Le téléphone du responsable du site est obligatoire."
            )
        if len(phone) < 8:
            raise serializers.ValidationError(
                "Saisissez un numéro valide (au moins 8 caractères)."
            )
        return phone

    def validate_site_sms_phone(self, value):
        phone = (value or "").strip()
        if phone and len(phone) < 8:
            raise serializers.ValidationError(
                "Saisissez un numéro SMS valide (au moins 8 caractères)."
            )
        return phone

    def create(self, validated_data):
        creation_date = validated_data.pop("creation_date", None)
        validated_data.setdefault("expected_start_time", time(6, 0))
        validated_data.setdefault("expected_end_time", time(18, 0))
        validated_data.setdefault("day_staff_required", 1)
        validated_data.setdefault("night_staff_required", 1)
        site = super().create(validated_data)
        if creation_date:
            site.created_at = timezone.make_aware(
                datetime.combine(creation_date, time(0, 0)),
                timezone.get_current_timezone(),
            )
            site.save(update_fields=["created_at"])
        return site

    def update(self, instance, validated_data):
        creation_date = validated_data.pop("creation_date", None)
        site = super().update(instance, validated_data)
        if creation_date:
            site.created_at = timezone.make_aware(
                datetime.combine(creation_date, time(0, 0)),
                timezone.get_current_timezone(),
            )
            site.save(update_fields=["created_at"])
        return site
