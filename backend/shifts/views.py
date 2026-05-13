from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import ShiftAssignment
from .serializers import ShiftAssignmentSerializer
from .services import ensure_assignments_for_dates


class TodayAssignmentsView(generics.ListAPIView):
    serializer_class = ShiftAssignmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        ensure_assignments_for_dates([yesterday, today])
        return (
            ShiftAssignment.objects.select_related("site")
            .filter(
                guard=self.request.user,
                # Couvre les postes de nuit qui démarrent à 18h et finissent le lendemain à 06h.
                shift_date__in=[yesterday, today],
            )
            .order_by("shift_date", "start_time")
        )
