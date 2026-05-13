from django.db import models
from django.conf import settings
from django.utils import timezone
from shifts.models import ShiftAssignment


class Checkin(models.Model):
    class Type(models.TextChoices):
        START = "start", "Start"
        END = "end", "End"
        PRESENCE = "presence", "Presence"

    assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, related_name="checkins")
    guard = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checkins")
    type = models.CharField(max_length=10, choices=Type.choices)
    timestamp = models.DateTimeField(auto_now_add=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    photo = models.ImageField(
        upload_to="checkins/",
        blank=True,
        null=True,
        help_text="Selfie obligatoire a chaque pointage (valide par l API).",
    )
    within_geofence = models.BooleanField(default=False)
    distance_from_site_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance calculée au centre de géofence du site (m, après enregistrement).",
    )
    device_id = models.CharField(max_length=120, blank=True)
    biometric_verified = models.BooleanField(default=False)
    biometric_score = models.FloatField(null=True, blank=True)
    biometric_provider = models.CharField(max_length=64, blank=True)
    biometric_checked_at = models.DateTimeField(null=True, blank=True)
    biometric_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self) -> str:
        return f"{self.guard} {self.type} at {self.timestamp}"


class BiometricVerification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    guard = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="biometric_verifications",
    )
    assignment = models.ForeignKey(
        ShiftAssignment,
        on_delete=models.CASCADE,
        related_name="biometric_verifications",
    )
    checkin_type = models.CharField(max_length=10, choices=Checkin.Type.choices)
    challenge_id = models.CharField(max_length=64, unique=True)
    nonce = models.CharField(max_length=64)
    device_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    score = models.FloatField(null=True, blank=True)
    provider = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    verification_token = models.CharField(max_length=128, blank=True)
    verification_token_expires_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.guard} {self.checkin_type} {self.status}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
