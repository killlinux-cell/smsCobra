from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from alerts.models import LateAlert
from reports.alert_ack import (
    PRESENCE_DECISION_ABSENT,
    PRESENCE_DECISION_PRESENT,
    acknowledge_assignment_late,
    acknowledge_late_alert,
    log_alert_acknowledged_to_report,
)
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

    def test_log_ack_present_marks_justified_presence(self):
        alert = LateAlert.objects.create(
            assignment=self.assignment,
            message="Retard prise de service : test",
            status=LateAlert.Status.ACKNOWLEDGED,
            admin_recipient=self.admin,
            acknowledged_at=timezone.now(),
        )
        log_alert_acknowledged_to_report(
            alert,
            self.admin,
            presence_decision=PRESENCE_DECISION_PRESENT,
        )
        report = AttendanceReport.objects.get(
            site=self.site,
            guard=self.guard,
            report_date=self.assignment.shift_date,
        )
        self.assertIn("présence justifiée", report.notes.lower())
        self.assertFalse(report.was_absent)
        self.assertIsNotNone(report.started_at)
        self.assertIsNotNone(report.ended_at)

    def test_log_ack_absent_marks_confirmed_absence(self):
        alert = LateAlert.objects.create(
            assignment=self.assignment,
            message="Absence: créneau terminé sans prise de service — test",
            status=LateAlert.Status.ACKNOWLEDGED,
            admin_recipient=self.admin,
            acknowledged_at=timezone.now(),
        )
        log_alert_acknowledged_to_report(
            alert,
            self.admin,
            presence_decision=PRESENCE_DECISION_ABSENT,
        )
        report = AttendanceReport.objects.get(
            site=self.site,
            guard=self.guard,
            report_date=self.assignment.shift_date,
        )
        self.assertIn("absence confirmée", report.notes.lower())
        self.assertTrue(report.was_absent)
        self.assertIsNone(report.started_at)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ShiftAssignment.Status.MISSED)

    def test_ack_assignment_late_absent(self):
        alert = acknowledge_assignment_late(
            self.assignment,
            self.admin,
            presence_decision=PRESENCE_DECISION_ABSENT,
        )
        self.assertEqual(alert.status, LateAlert.Status.ACKNOWLEDGED)
        report = AttendanceReport.objects.get(
            site=self.site,
            guard=self.guard,
            report_date=self.assignment.shift_date,
        )
        self.assertTrue(report.was_absent)

    def test_acknowledge_late_alert_present_default(self):
        alert = LateAlert.objects.create(
            assignment=self.assignment,
            message="Passation: relève absent",
        )
        acknowledge_late_alert(alert, self.admin)
        report = AttendanceReport.objects.get(
            site=self.site,
            guard=self.guard,
            report_date=self.assignment.shift_date,
        )
        self.assertFalse(report.was_absent)
