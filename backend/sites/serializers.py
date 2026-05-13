from datetime import time

from rest_framework import serializers

from .models import Site


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = "__all__"

    def create(self, validated_data):
        validated_data.setdefault("expected_start_time", time(6, 0))
        validated_data.setdefault("expected_end_time", time(18, 0))
        return super().create(validated_data)
