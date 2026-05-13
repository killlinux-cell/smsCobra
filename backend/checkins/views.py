from datetime import datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
import secrets
from zoneinfo import ZoneInfo
from django.conf import settings
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from alerts.models import LateAlert
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment
from .late_utils import is_start_late
from . import face_verify
from .models import BiometricVerification, Checkin
from .serializers import CheckinSerializer


# Quelques mètres de tolérance : arrondis flottants + imprécision Haversine / WGS84.
_GEOFENCE_COMPARE_SLACK_M = 3.0
_BIOMETRIC_CHALLENGE_TTL_SECONDS = 60
_BIOMETRIC_TOKEN_TTL_SECONDS = 60


def _distance_meters(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    r = 6371000
    d_lat = radians(float(lat2 - lat1))
    d_lon = radians(float(lon2 - lon1))
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(d_lon / 2) ** 2
    )
    # Évite un ValueError si le flottant dépasse légèrement 1 à cause des arrondis.
    a = min(1.0, max(0.0, a))
    return 2 * r * asin(sqrt(a))


def _site_tz(site):
    tz_name = (getattr(site, "timezone", None) or "").strip()
    if not tz_name:
        return timezone.get_current_timezone()
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.get_current_timezone()


def _assignment_window(assignment):
    """Fenêtre réelle du créneau (gère les postes de nuit qui finissent le lendemain)."""
    tz = _site_tz(assignment.site)
    start_at = datetime.combine(assignment.shift_date, assignment.start_time, tzinfo=tz)
    end_day = assignment.shift_date
    if assignment.end_time <= assignment.start_time:
        end_day = assignment.shift_date + timedelta(days=1)
    end_at = datetime.combine(end_day, assignment.end_time, tzinfo=tz)
    return start_at, end_at, tz


class CheckinBaseView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    checkin_type = None

    @property
    def biometric_enforced(self) -> bool:
        return getattr(settings, "BIOMETRIC_ENFORCEMENT_MODE", "enforce") == "enforce"

    def _validate_verification_token(self, request, assignment):
        verification_token = (request.data.get("verification_token") or "").strip()
        if not verification_token:
            if not self.biometric_enforced:
                return None, None
            return None, Response(
                {"verification_token": "Verification faciale obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        verification = BiometricVerification.objects.filter(
            verification_token=verification_token,
            guard=request.user,
            assignment=assignment,
            checkin_type=self.checkin_type,
            status=BiometricVerification.Status.VERIFIED,
        ).first()
        if not verification:
            return None, Response(
                {"detail": "Token biométrique invalide."},
                status=status.HTTP_403_FORBIDDEN,
            )
        now = timezone.now()
        if verification.consumed_at is not None:
            return None, Response(
                {"detail": "Token biométrique déjà utilisé."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if (
            verification.verification_token_expires_at is None
            or verification.verification_token_expires_at < now
        ):
            return None, Response(
                {"detail": "Token biométrique expiré."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return verification, None

    def post(self, request):
        raw_id = request.data.get("assignment")
        try:
            aid = int(raw_id)
        except (TypeError, ValueError):
            aid = None
        assignment = ShiftAssignment.objects.select_related("site").filter(
            id=aid,
            guard=request.user,
        ).first()
        if not assignment:
            return Response({"detail": "Affectation invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if self.checkin_type == Checkin.Type.START:
            start_at, end_at, site_tz = _assignment_window(assignment)
            now_local = timezone.now().astimezone(site_tz)
            if now_local < start_at or now_local > end_at:
                return Response(
                    {
                        "detail": (
                            "Prise de service hors créneau autorisé pour cette affectation "
                            f"({start_at.strftime('%d/%m/%Y %H:%M')} - {end_at.strftime('%d/%m/%Y %H:%M')})."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        verification, rejection = self._validate_verification_token(request, assignment)
        if rejection is not None:
            return rejection

        # Anti-doublon par affectation et par type
        if self.checkin_type == Checkin.Type.START:
            if Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists():
                return Response(
                    {"detail": "Prise de service deja effectuee pour cette affectation."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif self.checkin_type == Checkin.Type.END:
            if Checkin.objects.filter(assignment=assignment, type=Checkin.Type.END).exists():
                return Response(
                    {"detail": "Fin de service deja effectuee pour cette affectation."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif self.checkin_type == Checkin.Type.PRESENCE:
            # Pas de blocage temporel : plus d'alerte admin « 60 minutes » ; le vigile peut envoyer une présence quand nécessaire.
            pass

        serializer_data = request.data.copy()
        serializer_data.pop("verification_token", None)
        serializer = CheckinSerializer(data=serializer_data)
        serializer.is_valid(raise_exception=True)
        biometric_verified = verification is not None
        checkin = serializer.save(
            guard=request.user,
            type=self.checkin_type,
            biometric_verified=biometric_verified,
            biometric_score=verification.score if verification else None,
            biometric_provider=verification.provider if verification else "",
            biometric_checked_at=(verification.verified_at or timezone.now()) if verification else None,
            biometric_reason=verification.reason if verification else "observation_mode_bypass",
        )
        if verification is not None:
            verification.consumed_at = timezone.now()
            verification.save(update_fields=["consumed_at"])

        site = assignment.site
        distance = _distance_meters(
            checkin.latitude,
            checkin.longitude,
            site.latitude,
            site.longitude,
        )
        effective_radius = float(site.geofence_radius_meters + site.geofence_gps_margin_meters)
        checkin.distance_from_site_meters = round(distance, 1)
        checkin.within_geofence = distance <= effective_radius + _GEOFENCE_COMPARE_SLACK_M
        checkin.save(update_fields=["within_geofence", "distance_from_site_meters"])

        report, _ = AttendanceReport.objects.get_or_create(
            site=site,
            guard=request.user,
            report_date=assignment.shift_date,
        )
        if self.checkin_type == Checkin.Type.START:
            report.started_at = checkin.timestamp
            report.was_late = is_start_late(checkin.timestamp, assignment)
            report.save(update_fields=["started_at", "was_late"])
        elif self.checkin_type == Checkin.Type.END:
            report.ended_at = checkin.timestamp
            report.save(update_fields=["ended_at"])
        payload = dict(CheckinSerializer(checkin).data)
        payload["geofence_radius_meters"] = site.geofence_radius_meters
        payload["geofence_gps_margin_meters"] = site.geofence_gps_margin_meters
        payload["geofence_effective_radius_meters"] = effective_radius
        response = Response(payload, status=status.HTTP_201_CREATED)
        self._after_checkin_saved(assignment, checkin)
        return response

    def _after_checkin_saved(self, assignment, checkin):
        """Surchargé dans les vues début / fin pour notifications push et statuts."""
        pass


class StartCheckinView(CheckinBaseView):
    checkin_type = Checkin.Type.START

    def _after_checkin_saved(self, assignment, checkin):
        from alerts.services import (
            notify_pointage_start,
            resolve_passation_alerts_for_assignment,
            resolve_retard_alerts_for_assignment,
        )

        notify_pointage_start(assignment)
        resolve_retard_alerts_for_assignment(assignment)
        resolve_passation_alerts_for_assignment(assignment)


class EndCheckinView(CheckinBaseView):
    checkin_type = Checkin.Type.END

    def _after_checkin_saved(self, assignment, checkin):
        from alerts.services import (
            notify_pointage_end,
            resolve_fin_sans_pointage_alerts,
        )

        notify_pointage_end(assignment)
        resolve_fin_sans_pointage_alerts(assignment)
        if assignment.status in (
            ShiftAssignment.Status.SCHEDULED,
            ShiftAssignment.Status.REPLACED,
        ):
            ShiftAssignment.objects.filter(pk=assignment.pk).update(
                status=ShiftAssignment.Status.COMPLETED
            )
            assignment.status = ShiftAssignment.Status.COMPLETED

    def post(self, request):
        assignment = ShiftAssignment.objects.select_related("site").filter(
            id=request.data.get("assignment"),
            guard=request.user,
        ).first()
        if not assignment:
            return Response({"detail": "Affectation invalide."}, status=status.HTTP_400_BAD_REQUEST)

        if assignment.relieved_by_id:
            incoming = assignment.relieved_by
            if not Checkin.objects.filter(
                assignment=incoming,
                type=Checkin.Type.START,
            ).exists():
                return Response(
                    {
                        "detail": (
                            "Le vigile de releve doit d'abord pointer la prise de service sur son affectation "
                            f"(n°{incoming.id}) avant que vous puissiez terminer votre journee."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        resp = super().post(request)
        # Cloture les alertes de presence ouvertes une fois la fin de service enregistree.
        LateAlert.objects.filter(
            assignment=assignment,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="Presence:",
        ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())
        return resp


class PresenceCheckinView(CheckinBaseView):
    checkin_type = Checkin.Type.PRESENCE

    def post(self, request):
        # Presence ne doit etre enregistree qu'entre la prise de service et la fin.
        raw_id = request.data.get("assignment")
        try:
            aid = int(raw_id)
        except (TypeError, ValueError):
            aid = None
        assignment = ShiftAssignment.objects.select_related("site").filter(
            id=aid,
            guard=request.user,
        ).first()
        if not assignment:
            return Response({"detail": "Affectation invalide."}, status=status.HTTP_400_BAD_REQUEST)

        has_start = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.START).exists()
        has_end = Checkin.objects.filter(assignment=assignment, type=Checkin.Type.END).exists()
        if not has_start:
            return Response(
                {"detail": "La prise de service doit etre effectuee avant la presence."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if has_end:
            return Response(
                {"detail": "La fin de service a deja ete effectuee."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        resp = super().post(request)
        # Si une presence est enregistree, on cloture l'alerte de presence correspondante.
        LateAlert.objects.filter(
            assignment=assignment,
            status__in=[LateAlert.Status.OPEN, LateAlert.Status.ACKNOWLEDGED],
            message__startswith="Presence:",
        ).update(status=LateAlert.Status.RESOLVED, resolved_at=timezone.now())
        return resp


class BiometricChallengeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_id = request.data.get("assignment_id")
        checkin_type = (request.data.get("checkin_type") or "").strip()
        device_id = (request.data.get("device_id") or "").strip()
        try:
            aid = int(raw_id)
        except (TypeError, ValueError):
            aid = None
        if checkin_type not in Checkin.Type.values:
            return Response(
                {"checkin_type": "Type de pointage invalide."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = ShiftAssignment.objects.filter(id=aid, guard=request.user).first()
        if not assignment:
            return Response({"detail": "Affectation invalide."}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        challenge_id = secrets.token_hex(16)
        nonce = secrets.token_hex(16)
        verification = BiometricVerification.objects.create(
            guard=request.user,
            assignment=assignment,
            checkin_type=checkin_type,
            challenge_id=challenge_id,
            nonce=nonce,
            device_id=device_id,
            expires_at=now + timedelta(seconds=_BIOMETRIC_CHALLENGE_TTL_SECONDS),
        )
        return Response(
            {
                "challenge_id": verification.challenge_id,
                "nonce": verification.nonce,
                "expires_at": verification.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class BiometricVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        challenge_id = (request.data.get("challenge_id") or "").strip()
        selfie = request.data.get("selfie")
        verification = BiometricVerification.objects.filter(
            challenge_id=challenge_id,
            guard=request.user,
            status=BiometricVerification.Status.PENDING,
        ).first()
        if not verification:
            return Response(
                {"detail": "Challenge biométrique introuvable."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if verification.is_expired:
            verification.status = BiometricVerification.Status.REJECTED
            verification.reason = "challenge_expired"
            verification.save(update_fields=["status", "reason"])
            return Response(
                {"detail": "Challenge biométrique expiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if selfie is None:
            return Response(
                {"selfie": "Selfie obligatoire pour la vérification faciale."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.profile_photo:
            verification.status = BiometricVerification.Status.REJECTED
            verification.reason = "profile_photo_missing"
            verification.save(update_fields=["status", "reason"])
            return Response(
                {"detail": "Photo de référence absente pour ce vigile."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ok, match_score, fail_reason = face_verify.verify_selfie_against_profile(
            selfie, request.user.profile_photo
        )
        if not ok:
            verification.status = BiometricVerification.Status.REJECTED
            verification.reason = fail_reason or "face_verify_failed"
            if match_score is not None:
                verification.score = match_score
            verification.save(
                update_fields=["status", "reason", "score"],
            )
            messages = {
                "face_engine_unavailable": (
                    "Moteur de reconnaissance faciale indisponible sur le serveur. "
                    "Contactez l’administrateur (dépendance face-recognition / dlib)."
                ),
                "no_face_in_selfie": "Aucun visage détecté sur le selfie. Reprenez la photo, visage centré et bien éclairé.",
                "no_face_in_reference": (
                    "Photo d’enrôlement invalide : aucun visage détecté. "
                    "Mettez à jour la photo du vigile depuis le tableau de bord."
                ),
                "face_mismatch": "Le visage ne correspond pas à la photo d’enrôlement du vigile.",
                "face_verify_error": "Erreur technique lors de la comparaison faciale. Réessayez.",
            }
            detail = messages.get(fail_reason, "Vérification faciale refusée.")
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            if fail_reason in ("no_face_in_selfie", "no_face_in_reference"):
                http_status = status.HTTP_400_BAD_REQUEST
            elif fail_reason == "face_mismatch":
                http_status = status.HTTP_403_FORBIDDEN
            return Response(
                {"detail": detail, "reason": verification.reason},
                status=http_status,
            )

        token = secrets.token_urlsafe(32)
        now = timezone.now()
        verification.status = BiometricVerification.Status.VERIFIED
        verification.score = match_score if match_score is not None else 0.0
        verification.provider = "face_recognition"
        verification.reason = ""
        verification.verified_at = now
        verification.verification_token = token
        verification.verification_token_expires_at = now + timedelta(
            seconds=_BIOMETRIC_TOKEN_TTL_SECONDS
        )
        verification.save(
            update_fields=[
                "status",
                "score",
                "provider",
                "reason",
                "verified_at",
                "verification_token",
                "verification_token_expires_at",
            ]
        )
        return Response(
            {
                "verified": True,
                "score": verification.score,
                "verification_token": verification.verification_token,
                "expires_at": verification.verification_token_expires_at,
            },
            status=status.HTTP_200_OK,
        )
