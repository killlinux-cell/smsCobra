from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole
from shifts.models import ShiftAssignment
from sites.models import Site
from webadmin.alert_state import compute_replacement_needed, get_live_critical_alert_summary

from .models import LateAlert
from .serializers import (
    LateAlertSerializer,
    ReplacementNeededRowSerializer,
    ShiftAssignmentDispatchSerializer,
    VigileBriefSerializer,
)


class AlertListView(generics.ListAPIView):
    serializer_class = LateAlertSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        qs = LateAlert.objects.select_related(
            "assignment",
            "assignment__site",
            "assignment__guard",
        )
        st = (self.request.query_params.get("status") or "").strip().lower()
        if st == "open":
            qs = qs.filter(status=LateAlert.Status.OPEN)
        elif st in ("ack", "acknowledged", "acquitte"):
            qs = qs.filter(status=LateAlert.Status.ACKNOWLEDGED)
        return qs


class AckAlertView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, alert_id):
        alert = LateAlert.objects.filter(id=alert_id).first()
        if not alert:
            return Response({"detail": "Alerte introuvable."}, status=status.HTTP_404_NOT_FOUND)
        alert.status = LateAlert.Status.ACKNOWLEDGED
        alert.acknowledged_at = timezone.now()
        alert.admin_recipient = request.user
        alert.save(update_fields=["status", "acknowledged_at", "admin_recipient"])
        from reports.alert_ack import log_alert_acknowledged_to_report

        log_alert_acknowledged_to_report(alert, request.user)
        return Response(LateAlertSerializer(alert).data)


class DispatchReplacementView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        assignment = ShiftAssignment.objects.filter(id=request.data.get("assignment_id")).first()
        replacement_guard_id = request.data.get("replacement_guard_id")
        if not assignment or not replacement_guard_id:
            return Response({"detail": "Parametres invalides."}, status=status.HTTP_400_BAD_REQUEST)
        from .services import notify_dispatch_replacement

        previous_name = assignment.guard.display_name
        if int(replacement_guard_id) == assignment.guard_id:
            return Response({"detail": "Le remplaçant est deja en poste sur cette affectation."}, status=status.HTTP_400_BAD_REQUEST)
        absent_guard_id = assignment.guard_id
        update_fields = ["guard_id", "status"]
        if assignment.original_guard_id is None:
            assignment.original_guard_id = assignment.guard_id
            update_fields.append("original_guard_id")
        assignment.guard_id = replacement_guard_id
        assignment.status = ShiftAssignment.Status.REPLACED
        assignment.updated_at = timezone.now()
        update_fields.append("updated_at")
        assignment.save(update_fields=update_fields)

        from django.core.exceptions import ValidationError as DjangoValidationError
        from shifts.dispatch import process_dispatch_replacement

        promoted_post = None
        try:
            promoted_post = process_dispatch_replacement(
                assignment,
                absent_guard_id=absent_guard_id,
                replacement_guard_id=int(replacement_guard_id),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        notify_dispatch_replacement(assignment, previous_name)
        detail = "Remplacement enregistre."
        if promoted_post:
            detail = (
                f"Remplacement enregistre. {assignment.guard.display_name} est desormais titulaire "
                f"sur {promoted_post.site.name} ({promoted_post.get_shift_type_display()})."
            )
        return Response({"detail": detail})


class LiveStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        today = timezone.localdate()
        assignments = ShiftAssignment.objects.filter(shift_date=today)
        summary = get_live_critical_alert_summary(today)
        payload = {
            "total": assignments.count(),
            "scheduled": assignments.filter(status=ShiftAssignment.Status.SCHEDULED).count(),
            "replaced": assignments.filter(status=ShiftAssignment.Status.REPLACED).count(),
            "completed": assignments.filter(status=ShiftAssignment.Status.COMPLETED).count(),
            "missed": assignments.filter(status=ShiftAssignment.Status.MISSED).count(),
            "open_alerts": LateAlert.objects.filter(status=LateAlert.Status.OPEN).count(),
            "open_alerts_today": summary["alerts_open_count"],
            "replacement_needed_count": summary["replacement_needed_count"],
            "critical_count": summary["critical_count"],
            "extras_today": assignments.filter(status=ShiftAssignment.Status.EXTRA).count(),
            "vigiles_count": User.objects.filter(role=User.Role.VIGILE).count(),
            "sites_count": Site.objects.filter(is_active=True).count(),
        }
        return Response(payload)


class ReplacementNeededListView(APIView):
    """Postes sans prise de service après tolérance — comme le bandeau web."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        rows = compute_replacement_needed()
        data = ReplacementNeededRowSerializer(rows, many=True).data
        return Response(data)


class TodayAssignmentsDispatchView(generics.ListAPIView):
    """Affectations du jour pour dépêcher un remplaçant (mobile / outils)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = ShiftAssignmentDispatchSerializer

    def get_queryset(self):
        today = timezone.localdate()
        return (
            ShiftAssignment.objects.filter(shift_date=today)
            .select_related("site", "guard", "original_guard")
            .order_by("site__name", "start_time")
        )


class AdminVigilesListView(generics.ListAPIView):
    """Liste des vigiles pour choix remplaçant (sans affectation active aujourd'hui)."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VigileBriefSerializer

    def get_queryset(self):
        from shifts.dispatch_candidates import vigiles_free_today_queryset

        return vigiles_free_today_queryset()


class DispatchCandidatesView(APIView):
    """
    Vigiles disponibles pour remplacer sur une affectation donnée
    (libres sur le créneau, empreinte OK).
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        raw = (request.query_params.get("assignment_id") or "").strip()
        if not raw.isdigit():
            return Response(
                {"detail": "Paramètre assignment_id requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment = (
            ShiftAssignment.objects.select_related("site", "guard")
            .filter(pk=int(raw))
            .first()
        )
        if not assignment:
            return Response(
                {"detail": "Affectation introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        from shifts.dispatch_candidates import replacement_candidate_queryset

        qs = replacement_candidate_queryset(assignment)
        data = VigileBriefSerializer(
            qs,
            many=True,
            context={"request": request},
        ).data
        return Response(data)
