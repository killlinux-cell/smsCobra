from rest_framework import serializers

from .models import AttendanceReport


class AttendanceReportSerializer(serializers.ModelSerializer):
    site_name = serializers.CharField(source="site.name", read_only=True)
    guard_display = serializers.CharField(source="guard.display_name", read_only=True)

    class Meta:
        model = AttendanceReport
        fields = [
            "id",
            "site",
            "site_name",
            "guard",
            "guard_display",
            "report_date",
            "started_at",
            "ended_at",
            "was_late",
            "notes",
        ]
