from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from shifts.admin_serializers import (
    AdminShiftAssignmentCreateSerializer,
    AdminShiftAssignmentSerializer,
    AdminShiftAssignmentUpdateSerializer,
)
from shifts.models import ShiftAssignment
from shifts.services import ensure_assignments_for_dates


class AdminAssignmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminShiftAssignmentCreateSerializer
        return AdminShiftAssignmentSerializer

    def get_queryset(self):
        today = timezone.localdate()
        horizon = [today + timedelta(days=i) for i in range(31)]
        ensure_assignments_for_dates(horizon)

        qs = ShiftAssignment.objects.select_related(
            "site", "guard", "original_guard"
        ).order_by("shift_date", "start_time", "site__name")

        site_raw = (self.request.query_params.get("site") or "").strip()
        if site_raw.isdigit():
            qs = qs.filter(site_id=int(site_raw))

        status_raw = (self.request.query_params.get("status") or "").strip()
        if status_raw:
            qs = qs.filter(status=status_raw)

        date_from = (self.request.query_params.get("date_from") or "").strip()
        date_to = (self.request.query_params.get("date_to") or "").strip()
        if date_from:
            qs = qs.filter(shift_date__gte=date_from)
        else:
            qs = qs.filter(shift_date__gte=today)
        if date_to:
            qs = qs.filter(shift_date__lte=date_to)

        return qs

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignment = ser.save()
        mode = ser.validated_data.get("planning_mode")
        extra_days = ser.validated_data.get("extra_days") or 1
        if mode == "extra":
            detail = f"Renfort Extra planifié sur {extra_days} jour(s) consécutif(s)."
        else:
            detail = (
                "Affectation planifiée comme poste titulaire "
                "(reconduction automatique active)."
            )
        out = AdminShiftAssignmentSerializer(assignment, context={"request": request})
        return Response({"detail": detail, "assignment": out.data}, status=status.HTTP_201_CREATED)


class AdminAssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = ShiftAssignment.objects.select_related("site", "guard", "original_guard")

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AdminShiftAssignmentUpdateSerializer
        return AdminShiftAssignmentSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        out = AdminShiftAssignmentSerializer(assignment, context={"request": request})
        return Response(out.data)
