from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import ControllerSiteAssignment, ControllerVisit
from reports.controller_visits import build_controller_coverage_rows, build_controller_visit_report
from sites.models import Site

User = get_user_model()


class ControllerVisitReportTests(TestCase):
    def setUp(self):
        self.controller = User.objects.create_user(
            username="ctrl1",
            password="x",
            role=User.Role.CONTROLEUR,
            first_name="Jean",
            last_name="Ctrl",
        )
        self.site_a = Site.objects.create(
            name="TREICHVILLE",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.site_b = Site.objects.create(
            name="COCODY",
            address="B",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=2,
            longitude=2,
        )
        ControllerSiteAssignment.objects.create(
            controller=self.controller, site=self.site_a
        )
        ControllerSiteAssignment.objects.create(
            controller=self.controller, site=self.site_b
        )

    def test_coverage_marks_missing_sites(self):
        today = timezone.localdate()
        ControllerVisit.objects.create(
            controller=self.controller,
            site=self.site_a,
            face_score=0.65,
        )
        rows = build_controller_coverage_rows(today)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["present_on_day"])
        self.assertEqual(len(row["visited_sites"]), 1)
        self.assertEqual(len(row["missing_sites"]), 1)
        self.assertEqual(row["missing_sites"][0].name, "COCODY")

    def test_visit_report_includes_history(self):
        ControllerVisit.objects.create(
            controller=self.controller,
            site=self.site_a,
        )
        report = build_controller_visit_report()
        self.assertEqual(len(report["visit_history"]), 1)
        self.assertTrue(report["show_coverage"])

    def test_late_evening_visit_stays_on_same_local_day(self):
        """Un passage du 10/07 à 23h45 ne doit pas compter pour le 11/07."""
        tz = ZoneInfo("Africa/Abidjan")
        visit_time = datetime(2026, 7, 10, 23, 45, tzinfo=tz)
        ControllerVisit.objects.create(
            controller=self.controller,
            site=self.site_a,
            visited_at=visit_time,
        )
        rows_10 = build_controller_coverage_rows(date(2026, 7, 10))
        rows_11 = build_controller_coverage_rows(date(2026, 7, 11))
        self.assertEqual(len(rows_10), 1)
        self.assertTrue(rows_10[0]["present_on_day"])
        self.assertEqual(len(rows_10[0]["visits_on_day"]), 1)
        self.assertEqual(len(rows_11), 1)
        self.assertFalse(rows_11[0]["present_on_day"])
        self.assertEqual(len(rows_11[0]["visits_on_day"]), 0)
