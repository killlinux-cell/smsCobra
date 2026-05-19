from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from checkins.window import validate_end_window, validate_start_window
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class CheckinWindowTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Fenêtre",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        self.assignment = ShiftAssignment.objects.create(
            guard=User.objects.create_user(username="w", password="p", role="vigile"),
            site=self.site,
            shift_date=date(2026, 5, 19),
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        self.tz = ZoneInfo("Africa/Abidjan")

    def test_start_rejected_before_window(self):
        ts = datetime(2026, 5, 19, 5, 30, tzinfo=self.tz)
        ok, msg = validate_start_window(self.assignment, now=ts)
        self.assertFalse(ok)
        self.assertIn("hors créneau", msg or "")

    def test_end_rejected_before_scheduled_end(self):
        ts = datetime(2026, 5, 19, 10, 0, tzinfo=self.tz)
        ok, msg = validate_end_window(self.assignment, now=ts)
        self.assertFalse(ok)
        self.assertIn("trop tôt", msg or "")

    def test_end_allowed_at_scheduled_end(self):
        ts = datetime(2026, 5, 19, 18, 0, tzinfo=self.tz)
        ok, msg = validate_end_window(self.assignment, now=ts)
        self.assertTrue(ok)
        self.assertIsNone(msg)
