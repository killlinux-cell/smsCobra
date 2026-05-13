from django.db import models
from django.conf import settings
from shifts.models import ShiftAssignment


class LateAlert(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, related_name="late_alerts")
    admin_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_alerts",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    message = models.CharField(max_length=300)
    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-triggered_at",)

    def __str__(self) -> str:
        return f"Alert {self.assignment_id} - {self.status}"
