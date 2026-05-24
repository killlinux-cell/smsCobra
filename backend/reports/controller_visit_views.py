from datetime import datetime

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole

from .controller_visits import (
    build_controller_visit_report,
    serialize_controller_visit,
    serialize_coverage_row,
)


class ControllerVisitReportView(APIView):
    """Passages contrôleurs + couverture sites (superviseur / admin)."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        site_raw = request.query_params.get("site")
        date_raw = (request.query_params.get("date") or "").strip()
        month_raw = (request.query_params.get("month") or "").strip()

        site_id = int(site_raw) if site_raw and str(site_raw).isdigit() else None
        filter_day = None
        filter_month = None

        if date_raw:
            try:
                filter_day = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                filter_day = None
        elif month_raw:
            try:
                y_str, m_str = month_raw.split("-", 1)
                filter_month = (int(y_str), int(m_str))
            except (ValueError, IndexError):
                filter_month = None

        report = build_controller_visit_report(
            filter_day=filter_day,
            filter_month=filter_month,
            site_id=site_id,
        )
        return Response(
            {
                "coverage_date": (
                    report["coverage_date"].isoformat()
                    if report.get("coverage_date")
                    else None
                ),
                "show_coverage": report["show_coverage"],
                "coverage": [
                    serialize_coverage_row(row) for row in report["coverage_rows"]
                ],
                "visits": [
                    serialize_controller_visit(v) for v in report["visit_history"]
                ],
            }
        )
