from rest_framework import serializers

from .models import Checkin


class CheckinSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(required=True, allow_empty_file=False)

    class Meta:
        model = Checkin
        fields = "__all__"
        read_only_fields = ("timestamp", "within_geofence", "distance_from_site_meters", "guard", "type")

    def validate(self, attrs):
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        if lat is not None and lon is not None:
            la = float(lat)
            lo = float(lon)
            # « Null Island » ou GPS non prêt → distances absurdes côté serveur (milliers de km).
            if abs(la) < 1e-5 and abs(lo) < 1e-5:
                raise serializers.ValidationError(
                    {
                        "latitude": (
                            "Position GPS invalide (0°, 0°). Activez la localisation, mode haute précision, "
                            "puis réessayez à l’extérieur."
                        )
                    }
                )
            if abs(la) > 90 or abs(lo) > 180:
                raise serializers.ValidationError(
                    {"latitude": "Latitude ou longitude hors des plages valides."}
                )
        return attrs
