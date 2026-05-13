from django.db import models
from sites.models import Site
from django.conf import settings


class AttendanceReport(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="reports")
    guard = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    report_date = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    was_late = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("site", "guard", "report_date")

    def __str__(self) -> str:
        return f"{self.site} - {self.guard} - {self.report_date}"
