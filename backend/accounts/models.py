from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from sites.models import Site


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = "super_admin", "Super admin"
        ADMIN_SOCIETE = "admin_societe", "Admin societe"
        SUPERVISEUR = "superviseur", "Superviseur"
        CONTROLEUR = "controleur", "Controleur"
        VIGILE = "vigile", "Vigile"

    role = models.CharField(max_length=32, choices=Role.choices, default=Role.VIGILE)
    phone_number = models.CharField(max_length=20, blank=True)
    domicile = models.TextField(
        blank=True,
        help_text="Adresse ou lieu de résidence du vigile.",
    )
    is_active_on_duty = models.BooleanField(default=True)
    fcm_token = models.TextField(blank=True)
    profile_photo = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
        help_text="Photo portrait du vigile (obligatoire a la creation via le tableau de bord).",
    )
    aval = models.CharField(
        max_length=255,
        blank=True,
        help_text="Champ Aval (référence ou mention interne).",
    )
    date_integration = models.DateField(
        null=True,
        blank=True,
        help_text="Date d'intégration du vigile.",
    )
    id_document = models.FileField(
        upload_to="id_documents/",
        blank=True,
        null=True,
        help_text="Scan de la pièce d'identité (image ou PDF), via scanner ou fichier.",
    )

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"

    @property
    def display_name(self) -> str:
        full = self.get_full_name().strip()
        return f"{full} ({self.username})" if full else self.username


class ControllerSiteAssignment(models.Model):
    controller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="controller_site_assignments",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="controller_assignments",
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("controller", "site")
        indexes = [
            models.Index(fields=["site", "is_active"], name="ctrl_site_active_idx"),
            models.Index(fields=["controller", "is_active"], name="ctrl_guard_active_idx"),
        ]

    def clean(self):
        super().clean()
        if self.controller_id and self.controller.role != User.Role.CONTROLEUR:
            raise ValidationError({"controller": "L'utilisateur doit avoir le rôle contrôleur."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ControllerVisit(models.Model):
    controller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="controller_visits",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="controller_visits",
    )
    visited_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=120, blank=True)
    face_score = models.FloatField(null=True, blank=True)
    face_provider = models.CharField(max_length=64, default="face_recognition")

    class Meta:
        indexes = [
            models.Index(fields=["site", "visited_at"], name="ctrl_visit_site_time_idx"),
            models.Index(fields=["controller", "visited_at"], name="ctrl_visit_guard_time_idx"),
        ]

    def clean(self):
        super().clean()
        if self.controller_id and self.controller.role != User.Role.CONTROLEUR:
            raise ValidationError({"controller": "Le passage doit être enregistré par un contrôleur."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
