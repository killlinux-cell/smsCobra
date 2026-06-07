from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from alerts.models import LateAlert
from reports.alert_ack import log_alert_acknowledged_to_report
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class AlertAckReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_r",
            password="x",
            role=User.Role.ADMIN_SOCIETE,
            first_name="Paul",
            last_name="Dupont",
        )
        self.guard = User.objects.create_user(
            username="g_r", password="x", role=User.Role.VIGILE
        )
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time=time(6, 0),
            end_time=time(18, 0),
        )

    def test_log_ack_appends_notes_on_attendance_report(self):
        alert = LateAlert.objects.create(
            assignment=self.assignment,
            message="Retard prise de service : test",
            status=LateAlert.Status.ACKNOWLEDGED,
            admin_recipient=self.admin,
            acknowledged_at=timezone.now(),
        )
        log_alert_acknowledged_to_report(alert, self.admin)
        report = AttendanceReport.objects.get(
            site=self.site,
            guard=self.guard,
            report_date=self.assignment.shift_date,
        )
        self.assertIn("Paul", report.notes)
        self.assertIn("acquittée", report.notes.lower())
        self.assertFalse(report.was_absent)
        self.assertIsNotNone(report.started_at)
        self.assertIsNotNone(report.ended_at)
