from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole

from .models import AttendanceReport
from .serializers import AttendanceReportSerializer


class ReportListView(generics.ListAPIView):
    serializer_class = AttendanceReportSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = AttendanceReport.objects.select_related("site", "guard").all()
        site = self.request.query_params.get("site")
        report_date = self.request.query_params.get("date")
        month = (self.request.query_params.get("month") or "").strip()
        guard = self.request.query_params.get("guard")
        if site:
            queryset = queryset.filter(site_id=site)
        if guard and str(guard).isdigit():
            queryset = queryset.filter(guard_id=int(guard))
        if report_date:
            queryset = queryset.filter(report_date=report_date)
        elif month:
            try:
                y_str, m_str = month.split("-", 1)
                queryset = queryset.filter(
                    report_date__year=int(y_str),
                    report_date__month=int(m_str),
                )
            except (ValueError, IndexError):
                pass
        return queryset
