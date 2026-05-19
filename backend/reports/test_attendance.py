from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from checkins.models import Checkin
from reports.attendance import compute_was_absent, is_early_end, refresh_attendance_report
from reports.models import AttendanceReport
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class AttendanceAbsentTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="abs_guard", password="p", role="vigile")
        self.site = Site.objects.create(
            name="Site Abs",
            address="Abidjan",
            timezone="Africa/Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            late_tolerance_minutes=15,
            latitude=5.348,
            longitude=-4.024,
        )
        self.shift_day = date(2026, 5, 19)
        self.assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.shift_day,
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        self.tz = ZoneInfo("Africa/Abidjan")

    def test_is_early_end_before_scheduled_end(self):
        end_ts = datetime(2026, 5, 19, 17, 0, tzinfo=self.tz)
        self.assertTrue(is_early_end(end_ts, self.assignment))

    def test_is_not_early_end_at_scheduled_end(self):
        end_ts = datetime(2026, 5, 19, 18, 0, tzinfo=self.tz)
        self.assertFalse(is_early_end(end_ts, self.assignment))

    def test_absent_when_shift_over_without_start(self):
        after_shift = datetime(2026, 5, 19, 18, 20, tzinfo=self.tz)
        self.assertTrue(compute_was_absent(self.assignment, now=after_shift))

    def test_absent_when_start_without_end_after_shift(self):
        morning = datetime(2026, 5, 19, 6, 5, tzinfo=self.tz)
        start = Checkin.objects.create(
            guard=self.guard,
            assignment=self.assignment,
            type=Checkin.Type.START,
            latitude=5.348,
            longitude=-4.024,
        )
        Checkin.objects.filter(pk=start.pk).update(timestamp=morning)
        after_shift = datetime(2026, 5, 19, 18, 20, tzinfo=self.tz)
        self.assertTrue(compute_was_absent(self.assignment, now=after_shift))

    def test_not_absent_when_full_shift_completed_on_time(self):
        morning = datetime(2026, 5, 19, 6, 5, tzinfo=self.tz)
        evening = datetime(2026, 5, 19, 18, 5, tzinfo=self.tz)
        start = Checkin.objects.create(
            guard=self.guard,
            assignment=self.assignment,
            type=Checkin.Type.START,
            latitude=5.348,
            longitude=-4.024,
        )
        Checkin.objects.filter(pk=start.pk).update(timestamp=morning)
        end = Checkin.objects.create(
            guard=self.guard,
            assignment=self.assignment,
            type=Checkin.Type.END,
            latitude=5.348,
            longitude=-4.024,
        )
        Checkin.objects.filter(pk=end.pk).update(timestamp=evening)
        self.assertFalse(compute_was_absent(self.assignment, now=evening))

    def test_absent_when_early_end_recorded(self):
        morning = datetime(2026, 5, 19, 6, 5, tzinfo=self.tz)
        early = datetime(2026, 5, 19, 10, 0, tzinfo=self.tz)
        start = Checkin.objects.create(
            guard=self.guard,
            assignment=self.assignment,
            type=Checkin.Type.START,
            latitude=5.348,
            longitude=-4.024,
        )
        Checkin.objects.filter(pk=start.pk).update(timestamp=morning)
        end = Checkin.objects.create(
            guard=self.guard,
            assignment=self.assignment,
            type=Checkin.Type.END,
            latitude=5.348,
            longitude=-4.024,
        )
        Checkin.objects.filter(pk=end.pk).update(timestamp=early)
        self.assertTrue(compute_was_absent(self.assignment, now=early))

    def test_refresh_attendance_report_persists_was_absent(self):
        after_shift = datetime(2026, 5, 19, 18, 20, tzinfo=self.tz)
        report = refresh_attendance_report(self.assignment, now=after_shift)
        self.assertTrue(report.was_absent)
        report.refresh_from_db()
        self.assertTrue(AttendanceReport.objects.get(pk=report.pk).was_absent)
