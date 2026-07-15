from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from zoneinfo import ZoneInfo

from shifts.models import ShiftAssignment
from sites.models import Site
from alerts.models import LateAlert
from webadmin.alert_state import compute_replacement_needed

User = get_user_model()


class NightReplacementNeededTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="night_g", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site Nuit",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(18, 0),
            expected_end_time=time(6, 0),
            late_tolerance_minutes=15,
            relief_late_alert_minutes=45,
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

    def test_night_shift_not_marked_for_replacement_before_start(self):
        before_start = datetime(2026, 6, 2, 17, 0, tzinfo=self.tz)
        with patch("webadmin.alert_state.timezone.now", return_value=before_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(rows, [])

    def test_night_shift_listed_after_start_deadline(self):
        after_start = datetime(2026, 6, 2, 19, 0, tzinfo=self.tz)
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["assignment"].id, self.assignment.id)
        self.assertGreaterEqual(rows[0]["minutes_overdue"], 15)

    def test_night_shift_still_listed_after_wrong_missed_status(self):
        ShiftAssignment.objects.filter(pk=self.assignment.pk).update(
            status=ShiftAssignment.Status.MISSED
        )
        after_start = datetime(2026, 6, 2, 20, 0, tzinfo=self.tz)
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(len(rows), 1)

    def test_night_shift_from_yesterday_visible_early_morning(self):
        after_start = datetime(2026, 6, 3, 2, 0, tzinfo=self.tz)
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(date(2026, 6, 3))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["assignment"].id, self.assignment.id)

    def test_open_alert_id_attached_when_retard_alert_exists(self):
        after_start = datetime(2026, 6, 2, 19, 0, tzinfo=self.tz)
        alert = LateAlert.objects.create(
            assignment=self.assignment,
            message="Retard prise de service : night_g sur Site Nuit",
        )
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_alert_id"], alert.id)

    def test_acknowledged_passation_excluded_from_replacement_needed(self):
        after_start = datetime(2026, 6, 2, 19, 0, tzinfo=self.tz)
        LateAlert.objects.create(
            assignment=self.assignment,
            message="Passation: le releve n'a pas pris son service",
            status=LateAlert.Status.ACKNOWLEDGED,
        )
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(rows, [])

    def test_acknowledged_retard_excluded_from_replacement_needed(self):
        after_start = datetime(2026, 6, 2, 19, 0, tzinfo=self.tz)
        LateAlert.objects.create(
            assignment=self.assignment,
            message="Retard prise de service : night_g sur Site Nuit",
            status=LateAlert.Status.ACKNOWLEDGED,
        )
        with patch("webadmin.alert_state.timezone.now", return_value=after_start):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(rows, [])
