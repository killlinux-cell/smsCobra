from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from sites.models import Site


class ShiftAssignment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        REPLACED = "replaced", "Replaced"
        COMPLETED = "completed", "Completed"
        MISSED = "missed", "Missed"

    guard = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments")
    original_guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assignments_as_original_titular",
        help_text="Vigile titulaire d'origine lorsqu'un remplaçant a été désigné (dépêche).",
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="assignments")
    shift_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    relieved_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="outgoing_handover_assignments",
        help_text="Affectation du vigile de relève : sa prise de service est obligatoire avant la fin de service de ce créneau.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("guard", "site", "shift_date", "start_time")
        constraints = [
            models.UniqueConstraint(
                fields=["relieved_by"],
                condition=models.Q(relieved_by__isnull=False),
                name="uniq_shiftassignment_one_outgoing_per_incoming",
            ),
        ]
        indexes = [
            models.Index(
                fields=["site", "shift_date", "status"],
                name="shift_site_date_status_idx",
            ),
            models.Index(
                fields=["guard", "shift_date", "status"],
                name="shift_guard_date_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guard} @ {self.site} ({self.shift_date})"

    def clean(self):
        super().clean()
        if not self.relieved_by_id:
            return
        rb = self.relieved_by
        if rb.site_id != self.site_id:
            raise ValidationError(
                {"relieved_by": "Le relève doit être sur le même site que ce créneau."}
            )
        if rb.shift_date != self.shift_date:
            raise ValidationError(
                {"relieved_by": "Le relève doit être planifié le même jour."}
            )
        if rb.guard_id == self.guard_id:
            raise ValidationError(
                {"relieved_by": "Le vigile de relève doit être une autre personne."}
            )
        site = self.site
        if not site.relief_start_in_passation_windows(rb.start_time):
            raise ValidationError(
                {
                    "relieved_by": (
                        f"L'heure de début du relève ({rb.start_time.strftime('%H:%M')}) doit être dans une "
                        f"fenêtre de passation du site : matin "
                        f"{site.morning_passation_start.strftime('%H:%M')}–{site.morning_passation_end.strftime('%H:%M')} "
                        f"ou soir {site.evening_passation_start.strftime('%H:%M')}–"
                        f"{site.evening_passation_end.strftime('%H:%M')}."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class FixedPost(models.Model):
    class ShiftType(models.TextChoices):
        DAY = "day", "Jour (06:00-18:00)"
        NIGHT = "night", "Nuit (18:00-06:00)"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="fixed_posts")
    shift_type = models.CharField(max_length=8, choices=ShiftType.choices)
    titular_guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="titular_fixed_posts",
    )
    replacement_guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replacement_fixed_posts",
    )
    replacement_active = models.BooleanField(
        default=False,
        help_text="Si activé, le remplaçant tient le poste de façon continue.",
    )
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "shift_type"],
                condition=models.Q(is_active=True),
                name="uniq_active_fixedpost_per_site_shift",
            ),
        ]
        indexes = [
            models.Index(fields=["site", "shift_type", "is_active"], name="fxpost_site_shift_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.site.name} - {self.get_shift_type_display()} ({self.current_guard.display_name})"

    @property
    def current_guard(self):
        if self.replacement_active and self.replacement_guard_id:
            return self.replacement_guard
        return self.titular_guard
