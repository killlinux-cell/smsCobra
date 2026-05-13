from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from checkins.face_verify import verify_selfie_against_profile
from sites.models import Site
from shifts.models import ShiftAssignment
from shifts.services import ensure_assignments_for_dates

from .models import ControllerSiteAssignment, ControllerVisit, User
from .permissions import IsAdminRole
from .serializers import FCMTokenSerializer, UserSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class VigileFaceLoginView(APIView):
    """
    Connexion vigile sans mot de passe : identifiant + selfie comparé à la photo d'enrôlement.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        selfie = request.data.get("selfie")
        if not username:
            return Response(
                {"detail": "Identifiant requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if selfie is None:
            return Response(
                {"detail": "Selfie obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(username__iexact=username).first()
        if user is None or not user.is_active:
            return Response(
                {"detail": "Compte introuvable ou inactif."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if user.role != User.Role.VIGILE:
            return Response(
                {"detail": "Connexion par visage reservee aux vigiles."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.profile_photo:
            return Response(
                {
                    "detail": (
                        "Aucune photo d'enrôlement pour ce vigile. "
                        "Un administrateur doit ajouter une photo de profil."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ok, _score, fail_reason = verify_selfie_against_profile(selfie, user.profile_photo)
        if not ok:
            messages = {
                "face_engine_unavailable": "Service de reconnaissance faciale indisponible sur le serveur.",
                "no_face_in_selfie": "Aucun visage détecté sur le selfie. Réessayez avec un meilleur cadrage.",
                "no_face_in_reference": "Photo d'enrôlement invalide. Contactez l'administrateur.",
                "face_mismatch": "Le visage ne correspond pas au vigile enregistré.",
                "face_verify_error": "Erreur technique lors de la comparaison faciale.",
            }
            detail = messages.get(fail_reason, "Verification faciale refusee.")
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            if fail_reason in ("no_face_in_selfie", "no_face_in_reference"):
                http_status = status.HTTP_400_BAD_REQUEST
            elif fail_reason == "face_mismatch":
                http_status = status.HTTP_401_UNAUTHORIZED
            return Response({"detail": detail, "reason": fail_reason}, status=http_status)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )


class VigileFaceIdentifyView(APIView):
    """
    Connexion vigile sans identifiant: selfie -> identification du vigile planifié.
    Refuse si le visage ne correspond à aucun vigile ayant un service aujourd'hui.

    ``site_id`` (optionnel) restreint les candidats au site donné (moins de comparaisons,
    évite les homonymes visuels entre sites). Sans ``site_id``, tous les services
    d'hier et d'aujourd'hui sont pris en compte.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        selfie = request.data.get("selfie")
        site_id_raw = request.data.get("site_id")
        if selfie is None:
            return Response(
                {"detail": "Selfie obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        site_id = None
        if site_id_raw is not None and str(site_id_raw).strip() != "":
            try:
                site_id = int(site_id_raw)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "site_id invalide."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if site_id <= 0:
                return Response(
                    {"detail": "site_id invalide."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        ensure_assignments_for_dates([yesterday, today])
        planned_qs = ShiftAssignment.objects.filter(
            shift_date__in=[yesterday, today],
            status__in=[ShiftAssignment.Status.SCHEDULED, ShiftAssignment.Status.REPLACED],
        )
        if site_id is not None:
            planned_qs = planned_qs.filter(site_id=site_id)
        planned_guard_ids = planned_qs.values_list("guard_id", flat=True).distinct()
        candidates = User.objects.filter(
            id__in=planned_guard_ids,
            role=User.Role.VIGILE,
            is_active=True,
        ).exclude(profile_photo="")

        if not candidates.exists():
            detail = (
                "Aucun vigile planifié sur ce site avec photo d'enrôlement."
                if site_id is not None
                else "Aucun vigile planifié avec photo d'enrôlement sur les créneaux récents."
            )
            return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)

        best_user = None
        best_score = -1.0
        for candidate in candidates:
            if not candidate.profile_photo:
                continue
            ok, score, fail_reason = verify_selfie_against_profile(selfie, candidate.profile_photo)
            if fail_reason == "no_face_in_selfie":
                return Response(
                    {
                        "detail": "Aucun visage détecté sur le selfie. Reprenez la photo avec un meilleur cadrage."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ok and score is not None and score > best_score:
                best_user = candidate
                best_score = score
            try:
                selfie.seek(0)
            except Exception:
                pass

        if best_user is None:
            return Response(
                {
                    "detail": (
                        "Visage non reconnu ou vigile non planifié aujourd'hui. "
                        "Accès refusé."
                    )
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(best_user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "guard_username": best_user.username,
                "guard_name": best_user.display_name,
            },
            status=status.HTTP_200_OK,
        )


class ControllerFaceCheckinView(APIView):
    """
    Pointage de passage contrôleur sur un site via reconnaissance faciale.
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        selfie = request.data.get("selfie")
        site_id_raw = request.data.get("site_id")
        device_id = (request.data.get("device_id") or "").strip()
        if selfie is None:
            return Response({"detail": "Selfie obligatoire."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            site_id = int(site_id_raw)
        except (TypeError, ValueError):
            site_id = None
        if not site_id:
            return Response({"detail": "site_id invalide."}, status=status.HTTP_400_BAD_REQUEST)

        site = Site.objects.filter(id=site_id, is_active=True).first()
        if not site:
            return Response({"detail": "Site introuvable ou inactif."}, status=status.HTTP_404_NOT_FOUND)

        assignments = (
            ControllerSiteAssignment.objects.select_related("controller")
            .filter(site=site, is_active=True, controller__is_active=True)
            .exclude(controller__profile_photo="")
        )
        candidates = [a.controller for a in assignments if a.controller.profile_photo]
        if not candidates:
            return Response(
                {"detail": "Aucun contrôleur actif avec photo n'est affecté à ce site."},
                status=status.HTTP_403_FORBIDDEN,
            )

        best_user = None
        best_score = -1.0
        for candidate in candidates:
            ok, score, fail_reason = verify_selfie_against_profile(selfie, candidate.profile_photo)
            if fail_reason == "no_face_in_selfie":
                return Response(
                    {"detail": "Aucun visage détecté sur le selfie. Reprenez la photo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ok and score is not None and score > best_score:
                best_user = candidate
                best_score = score
            try:
                selfie.seek(0)
            except Exception:
                pass

        if best_user is None:
            return Response(
                {"detail": "Visage non reconnu pour un contrôleur autorisé sur ce site."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        now = timezone.now()
        recent = ControllerVisit.objects.filter(
            controller=best_user,
            site=site,
            visited_at__gte=now - timedelta(minutes=3),
        ).first()
        created = recent is None
        visit = recent
        if created:
            visit = ControllerVisit.objects.create(
                controller=best_user,
                site=site,
                device_id=device_id,
                face_score=best_score if best_score >= 0 else None,
            )

        return Response(
            {
                "ok": True,
                "created": created,
                "controller_id": best_user.id,
                "controller_name": best_user.display_name,
                "site_id": site.id,
                "site_name": site.name,
                "visited_at": visit.visited_at,
                "face_score": best_score if best_score >= 0 else None,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class EntrySitesView(APIView):
    """
    Liste minimale des sites actifs pour écran de pointage (vigile/contrôleur).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        data = [
            {"id": s.id, "name": s.name}
            for s in Site.objects.filter(is_active=True).order_by("name").only("id", "name")
        ]
        return Response(data, status=status.HTTP_200_OK)


class FCMTokenView(APIView):
    """
    Enregistre le token FCM du compte connecté pour recevoir les alertes push.
    Réservé aux rôles admin (super_admin, admin_societe, superviseur).
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        ser = FCMTokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data["fcm_token"]
        request.user.fcm_token = token
        request.user.save(update_fields=["fcm_token"])
        return Response({"detail": "Token FCM enregistré."}, status=status.HTTP_200_OK)

    def delete(self, request):
        request.user.fcm_token = ""
        request.user.save(update_fields=["fcm_token"])
        return Response({"detail": "Token FCM supprimé."}, status=status.HTTP_200_OK)
