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
            with patch("alerts.tasks.timezone.localdate", return_value=self.shift_day):
                detect_missed_shift_task()
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ShiftAssignment.Status.SCHEDULED)


class NightOnlyInvertedSiteAlertTests(TestCase):
    """Pas d'alerte retard le matin pour un site 0 jour / 1 nuit (19h→7h)."""

    def setUp(self):
        self.guard = User.objects.create_user(username="gill_g", password="x", role="vigile")
        self.site = Site.objects.create(
            name="GILL LANDY",
            address="MBADON",
            timezone="Africa/Abidjan",
            expected_start_time=time(19, 0),
            expected_end_time=time(7, 0),
            day_staff_required=0,
            night_staff_required=1,
            late_tolerance_minutes=30,
            latitude=1,
            longitude=1,
        )
        self.shift_day = date(2026, 6, 16)
        self.assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(19, 0),
            end_time=time(7, 0),
        )
        self.tz = ZoneInfo("Africa/Abidjan")

    @patch("alerts.tasks.send_push_to_admins")
    @patch("alerts.tasks.ensure_assignments_for_dates")
    def test_no_late_alert_morning_before_19h_start(self, _ensure, _push):
        morning = datetime(2026, 6, 16, 8, 0, tzinfo=self.tz)
        with patch("alerts.tasks.timezone.now", return_value=morning):
            with patch("alerts.tasks.timezone.localdate", return_value=self.shift_day):
                detect_missed_shift_task()
        from alerts.models import LateAlert

        self.assertFalse(
            LateAlert.objects.filter(message__startswith="Retard prise de service").exists()
        )

    @patch("alerts.tasks.send_push_to_admins")
    @patch("alerts.tasks.ensure_assignments_for_dates")
    def test_spurious_07_assignment_ignored_morning(self, _ensure, _push):
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(7, 0),
            end_time=time(19, 0),
        )
        morning = datetime(2026, 6, 16, 8, 30, tzinfo=self.tz)
        with patch("alerts.tasks.timezone.now", return_value=morning):
            with patch("alerts.tasks.timezone.localdate", return_value=self.shift_day):
                detect_missed_shift_task()
        from alerts.models import LateAlert

        self.assertFalse(
            LateAlert.objects.filter(message__startswith="Retard prise de service").exists()
        )
