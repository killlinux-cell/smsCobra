from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminRole
from shifts.models import ShiftAssignment

from .models import LateAlert
from .serializers import (
    LateAlertSerializer,
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
        alert.save()
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
        update_fields = ["guard_id", "status"]
        if assignment.original_guard_id is None:
            assignment.original_guard_id = assignment.guard_id
            update_fields.append("original_guard_id")
        assignment.guard_id = replacement_guard_id
        assignment.status = ShiftAssignment.Status.REPLACED
        assignment.updated_at = timezone.now()
        update_fields.append("updated_at")
        assignment.save(update_fields=update_fields)
        notify_dispatch_replacement(assignment, previous_name)
        return Response({"detail": "Remplacement enregistre."})


class LiveStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        today = timezone.localdate()
        assignments = ShiftAssignment.objects.filter(shift_date=today)
        payload = {
            "total": assignments.count(),
            "scheduled": assignments.filter(status=ShiftAssignment.Status.SCHEDULED).count(),
            "replaced": assignments.filter(status=ShiftAssignment.Status.REPLACED).count(),
            "completed": assignments.filter(status=ShiftAssignment.Status.COMPLETED).count(),
            "missed": assignments.filter(status=ShiftAssignment.Status.MISSED).count(),
            "open_alerts": LateAlert.objects.filter(status=LateAlert.Status.OPEN).count(),
        }
        return Response(payload)


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
    """Liste des vigiles pour choix remplaçant."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = VigileBriefSerializer

    def get_queryset(self):
        return User.objects.filter(role=User.Role.VIGILE).order_by("username")
