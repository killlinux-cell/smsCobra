from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from zoneinfo import ZoneInfo

from alerts.models import LateAlert
from alerts.tasks import detect_missed_shift_task
from reports.alert_ack import acknowledge_assignment_late
from shifts.models import ShiftAssignment
from sites.models import Site
from webadmin.alert_state import compute_replacement_needed

User = get_user_model()


class AlertAckPersistenceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_ack",
            password="secret",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.guard = User.objects.create_user(username="night_ack", password="x", role="vigile")
        self.site = Site.objects.create(
            name="CAFE BEIROUT",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(19, 0),
            expected_end_time=time(7, 0),
            day_staff_required=0,
            night_staff_required=1,
            late_tolerance_minutes=30,
            latitude=1,
            longitude=1,
        )
        self.shift_day = date(2026, 7, 21)
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
    def test_present_ack_stays_hidden_after_rescan(self, _ensure, _push):
        evening = datetime(2026, 7, 21, 23, 0, tzinfo=self.tz)
        acknowledge_assignment_late(
            self.assignment,
            self.admin,
            presence_decision="present",
        )
        with patch("alerts.tasks.timezone.now", return_value=evening):
            with patch("alerts.tasks.timezone.localdate", return_value=self.shift_day):
                detect_missed_shift_task()
        with patch("webadmin.alert_state.timezone.now", return_value=evening):
            rows = compute_replacement_needed(self.shift_day)
        self.assertEqual(rows, [])
        self.assertFalse(
            LateAlert.objects.filter(
                assignment=self.assignment,
                status=LateAlert.Status.OPEN,
            ).exists()
        )
