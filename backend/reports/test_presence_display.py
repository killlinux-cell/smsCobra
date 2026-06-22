from datetime import time, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from reports.models import AttendanceReport
from reports.presence_display import report_presence_badge
from sites.models import Site


class ReportPresenceDisplayTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="VIR-009", password="x", role="vigile")
        self.site = Site.objects.create(
            name="S",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)

    def _report(self, shift_date, *, started=True, ended=False, was_absent=False):
        return AttendanceReport.objects.create(
            site=self.site,
            guard=self.guard,
            report_date=shift_date,
            started_at=timezone.now() if started else None,
            ended_at=timezone.now() if ended else None,
            was_absent=was_absent,
        )

    def test_start_only_past_day_is_incomplete_not_present(self):
        badge = report_presence_badge(
            self._report(self.yesterday, started=True, ended=False)
        )
        self.assertEqual(badge["code"], "incomplete")
        self.assertEqual(badge["label"], "Fin non pointée")

    def test_start_only_today_is_in_service(self):
        badge = report_presence_badge(
            self._report(self.today, started=True, ended=False)
        )
        self.assertEqual(badge["code"], "in_service")

    def test_full_day_is_present(self):
        badge = report_presence_badge(
            self._report(self.yesterday, started=True, ended=True)
        )
        self.assertEqual(badge["code"], "present")
