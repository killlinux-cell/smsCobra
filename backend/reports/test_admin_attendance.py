from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from checkins.models import Checkin
from reports.admin_attendance import (
    MANUAL_CORRECTION_MARKER,
    admin_adjust_attendance_report,
    report_presence_locked_by_supervisor,
)
from reports.attendance import refresh_attendance_report
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class AdminAttendanceAdjustTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="owner_admin",
            password="secret",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.guard = User.objects.create_user(username="vigile_adj", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site Adj",
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
        self.shift_day = date(2026, 7, 20)
        self.assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(19, 0),
            end_time=time(7, 0),
            status=ShiftAssignment.Status.MISSED,
        )
        self.report = AttendanceReport.objects.create(
            site=self.site,
            guard=self.guard,
            report_date=self.shift_day,
            was_absent=True,
        )
        self.tz = ZoneInfo("Africa/Abidjan")

    def test_mark_present_clears_absence_and_logs_note(self):
        admin_adjust_attendance_report(
            self.report,
            presence_decision="present",
            actor=self.admin,
            reason="Acquittement superviseur erroné",
        )
        self.report.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertFalse(self.report.was_absent)
        self.assertIsNotNone(self.report.started_at)
        self.assertIn(MANUAL_CORRECTION_MARKER, self.report.notes)
        self.assertEqual(self.assignment.status, ShiftAssignment.Status.SCHEDULED)

    def test_mark_absent_after_wrong_present_ack(self):
        admin_adjust_attendance_report(
            self.report,
            presence_decision="present",
            actor=self.admin,
            reason="Erreur initiale",
        )
        admin_adjust_attendance_report(
            self.report,
            presence_decision="absent",
            actor=self.admin,
            reason="Vigile réellement absent confirmé",
        )
        self.report.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertTrue(self.report.was_absent)
        self.assertIsNone(self.report.started_at)
        self.assertEqual(self.assignment.status, ShiftAssignment.Status.MISSED)

    def test_manual_correction_not_overwritten_by_refresh(self):
        admin_adjust_attendance_report(
            self.report,
            presence_decision="present",
            actor=self.admin,
            reason="Correction admin",
        )
        self.assertTrue(report_presence_locked_by_supervisor(self.report))
        after_shift = datetime(2026, 7, 21, 8, 0, tzinfo=self.tz)
        refresh_attendance_report(self.assignment, now=after_shift)
        self.report.refresh_from_db()
        self.assertFalse(self.report.was_absent)

    def test_reason_required(self):
        with self.assertRaises(ValidationError):
            admin_adjust_attendance_report(
                self.report,
                presence_decision="absent",
                actor=self.admin,
                reason="",
            )

    def test_does_not_clear_times_when_real_checkin_exists(self):
        Checkin.objects.create(
            assignment=self.assignment,
            guard=self.guard,
            type=Checkin.Type.START,
            timestamp=datetime(2026, 7, 20, 19, 5, tzinfo=self.tz),
            latitude=1,
            longitude=1,
        )
        self.report.started_at = datetime(2026, 7, 20, 19, 5, tzinfo=self.tz)
        self.report.ended_at = datetime(2026, 7, 21, 7, 0, tzinfo=self.tz)
        self.report.was_absent = False
        self.report.save()
        admin_adjust_attendance_report(
            self.report,
            presence_decision="absent",
            actor=self.admin,
            reason="Finalement absent malgré pointage erroné",
        )
        self.report.refresh_from_db()
        self.assertTrue(self.report.was_absent)
        self.assertIsNotNone(self.report.started_at)
