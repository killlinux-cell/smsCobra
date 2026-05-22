from datetime import time

from rest_framework import serializers

from .models import Site


class SiteSerializer(serializers.ModelSerializer):
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
                "Le numéro du responsable du site est obligatoire."
            )
        if len(phone) < 8:
            raise serializers.ValidationError(
                "Saisissez un numéro valide (au moins 8 caractères)."
            )
        return phone

    def create(self, validated_data):
        validated_data.setdefault("expected_start_time", time(6, 0))
        validated_data.setdefault("expected_end_time", time(18, 0))
        return super().create(validated_data)
