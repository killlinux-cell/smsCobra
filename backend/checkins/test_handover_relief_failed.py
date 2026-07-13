"""Tests passation : relève absent ne bloque plus indéfiniment la fin de nuit."""

from datetime import date, datetime, time
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from zoneinfo import ZoneInfo

from accounts.models import User
from checkins.models import Checkin
from checkins.handover import incoming_relief_is_failed
from shifts.models import ShiftAssignment
from sites.models import Site


class ReliefFailedHandoverTests(TestCase):
    """Site 3 jour + 3 nuit : un vigile jour absent ne bloque plus la nuit indéfiniment."""

    shift_day = date(2026, 7, 13)
    next_day = date(2026, 7, 14)

    def setUp(self):
        self.tz = ZoneInfo("Africa/Abidjan")
        self.site = Site.objects.create(
            name="Direction conseil régional",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            late_tolerance_minutes=15,
            relief_late_alert_minutes=45,
            latitude=5.348,
            longitude=-4.024,
        )
        self.day_absent = User.objects.create_user(
            username="VIR-DAY-A",
            password="x",
            role="vigile",
            first_name="Absent",
        )
        self.night_guard = User.objects.create_user(
            username="VIR-021",
            password="x",
            role="vigile",
            first_name="Nuit",
        )
        self.day_ok = User.objects.create_user(
            username="VIR-DAY-B",
            password="x",
            role="vigile",
            first_name="Present",
        )
        self.night_shift = ShiftAssignment.objects.create(
            guard=self.night_guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(18, 30),
            end_time=time(6, 30),
        )
        self.day_relief = ShiftAssignment.objects.create(
            guard=self.day_absent,
            site=self.site,
            shift_date=self.next_day,
            start_time=time(6, 30),
            end_time=time(18, 30),
        )
        self.night_shift.relieved_by = self.day_relief
        self.night_shift.save(update_fields=["relieved_by"])

        Checkin.objects.create(
            guard=self.night_guard,
            assignment=self.night_shift,
            type=Checkin.Type.START,
            latitude=5.348,
            longitude=-4.024,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.night_guard)

    def test_incoming_relief_failed_after_grace(self):
        late_morning = datetime(2026, 7, 14, 7, 30, tzinfo=self.tz)
        with patch("checkins.handover.timezone.now", return_value=late_morning):
            self.assertTrue(incoming_relief_is_failed(self.day_relief))

    def test_night_end_allowed_when_day_relief_absent(self):
        late_morning = datetime(2026, 7, 14, 7, 30, tzinfo=self.tz)
        with patch("checkins.views.timezone.now", return_value=late_morning):
            resp = self.client.post(
                "/api/v1/checkins/end",
                {
                    "assignment": str(self.night_shift.id),
                    "latitude": "5.348",
                    "longitude": "-4.024",
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            Checkin.objects.filter(
                assignment=self.night_shift,
                type=Checkin.Type.END,
            ).exists()
        )

    def test_night_end_still_blocked_before_relief_grace_expires(self):
        just_after_shift_end = datetime(2026, 7, 14, 6, 45, tzinfo=self.tz)
        with patch("checkins.views.timezone.now", return_value=just_after_shift_end):
            resp = self.client.post(
                "/api/v1/checkins/end",
                {
                    "assignment": str(self.night_shift.id),
                    "latitude": "5.348",
                    "longitude": "-4.024",
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("relève", resp.data.get("detail", "").lower())

    def test_day_guard_unrelated_can_start_while_colleague_absent(self):
        day_assignment = ShiftAssignment.objects.create(
            guard=self.day_ok,
            site=self.site,
            shift_date=self.next_day,
            start_time=time(6, 30),
            end_time=time(18, 30),
        )
        morning = datetime(2026, 7, 14, 6, 35, tzinfo=self.tz)
        client_b = APIClient()
        client_b.force_authenticate(self.day_ok)
        with patch("checkins.views.timezone.now", return_value=morning):
            resp = client_b.post(
                "/api/v1/checkins/start",
                {
                    "assignment": str(day_assignment.id),
                    "latitude": "5.348",
                    "longitude": "-4.024",
                },
                format="multipart",
            )
        self.assertEqual(resp.status_code, 201)
