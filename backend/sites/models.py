from datetime import time

from django.db import models
from django.utils.dateparse import parse_time


class Site(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    timezone = models.CharField(max_length=64, default="Africa/Abidjan")
    expected_start_time = models.TimeField()
    expected_end_time = models.TimeField()
    late_tolerance_minutes = models.PositiveSmallIntegerField(default=15)
    morning_passation_start = models.TimeField(
        default=time(6, 0),
        help_text="Début fenêtre passation matin (ex. relève nuit → jour), indicatif planning.",
    )
    morning_passation_end = models.TimeField(default=time(7, 0))
    evening_passation_start = models.TimeField(
        default=time(18, 0),
        help_text="Début fenêtre passation soir (ex. relève jour → nuit), indicatif planning.",
    )
    evening_passation_end = models.TimeField(default=time(19, 0))
    relief_late_alert_minutes = models.PositiveSmallIntegerField(
        default=45,
        help_text="Après l'heure de prise de service du relève, délai avant alerte admin (minutes).",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    geofence_radius_meters = models.PositiveIntegerField(default=250)
    geofence_gps_margin_meters = models.PositiveSmallIntegerField(
        default=75,
        help_text=(
            "Marge ajoutée au rayon pour l'imprécision GPS des téléphones (réduit les faux « hors zone »). "
            "Mettre 0 pour un contrôle strict."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def relief_start_in_passation_windows(self, start_time) -> bool:
        """True si l'heure de prise de service du relève est dans la fenêtre matin ou soir du site."""

        def _t(v):
            if hasattr(v, "hour"):
                return v
            if isinstance(v, str):
                return parse_time(v) or v
            return v

        st = _t(start_time)
        ms, me = _t(self.morning_passation_start), _t(self.morning_passation_end)
        es, ee = _t(self.evening_passation_start), _t(self.evening_passation_end)
        if not all(hasattr(x, "hour") for x in (st, ms, me, es, ee)):
            return False
        in_morning = ms <= st <= me
        in_evening = es <= st <= ee
        return in_morning or in_evening
