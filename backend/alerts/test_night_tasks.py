from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from zoneinfo import ZoneInfo

from alerts.tasks import detect_missed_shift_task
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class NightShiftAbsenceDetectionTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="night_abs", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site Nuit",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(18, 0),
            expected_end_time=time(6, 0),
            late_tolerance_minutes=15,
            latitude=1,
            longitude=1,
        )
        self.shift_day = date(2026, 6, 2)
        self.assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(18, 0),
            end_time=time(6, 0),
        )
        self.tz = ZoneInfo("Africa/Abidjan")

    @patch("alerts.tasks.send_push_to_admins")
    @patch("alerts.tasks.ensure_assignments_for_dates")
    def test_night_shift_not_marked_missed_before_evening(self, _ensure, _push):
        morning = datetime(2026, 6, 2, 10, 0, tzinfo=self.tz)
        with patch("alerts.tasks.timezone.now", return_value=morning):
            with patch("alerts.tasks.date") as mock_date:
                mock_date.today.return_value = self.shift_day
                detect_missed_shift_task()
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ShiftAssignment.Status.SCHEDULED)
