from django.conf import settings
from django.db import models

from sites.models import Site


class AttendanceReport(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="reports")
    guard = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    report_date = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    was_late = models.BooleanField(default=False)
    was_absent = models.BooleanField(
        default=False,
        help_text=(
            "Journée comptée absente : pas de prise de service, fin non pointée "
            "après le créneau, ou fin avant l'heure prévue."
        ),
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("site", "guard", "report_date")

    def __str__(self) -> str:
        return f"{self.site} - {self.guard} - {self.report_date}"


class TitularChangeLog(models.Model):
    """Historique promotion / réintégration titulaire (rapports et journal d'activité)."""

    class Kind(models.TextChoices):
        PROMOTED = "titular_promoted", "Promotion titulaire"
        REINSTATED = "titular_reinstated", "Réintégration titulaire"
        RETIRED = "titular_retired", "Retrait titulaire"

    kind = models.CharField(max_length=32, choices=Kind.choices)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="titular_change_logs")
    fixed_post = models.ForeignKey(
        "shifts.FixedPost",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="titular_change_logs",
    )
    shift_type = models.CharField(max_length=8, blank=True)
    from_guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="titular_changes_from",
    )
    to_guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="titular_changes_to",
    )
    reason = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="titular_changes_as_actor",
    )
    assignment = models.ForeignKey(
        "shifts.ShiftAssignment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="titular_change_logs",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["site", "occurred_at"], name="titular_chg_site_time_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.site_id} @ {self.occurred_at}"
