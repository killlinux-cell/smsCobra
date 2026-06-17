from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from checkins.models import Checkin
from shifts.models import ShiftAssignment
from shifts.realign_assignment_times import (
    apply_realign_scheduled_assignment_times,
    plan_realign_scheduled_assignment_times,
)
from sites.models import Site


class RealignAssignmentTimesTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="g_r", password="x", role="vigile")
        self.site = Site.objects.create(
            name="King",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.today = timezone.localdate()

    def test_plan_finds_legacy_scheduled_only(self):
        legacy = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today + timedelta(days=2),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        started = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today + timedelta(days=3),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        Checkin.objects.create(
            guard=self.guard,
            assignment=started,
            type=Checkin.Type.START,
            latitude=1,
            longitude=1,
        )
        plan = plan_realign_scheduled_assignment_times(from_date=self.today)
        ids = {row.assignment_id for row in plan.candidates}
        self.assertIn(legacy.id, ids)
        self.assertNotIn(started.id, ids)
        self.assertEqual(plan.skipped_has_start, 1)

    def test_apply_updates_future_legacy_row(self):
        row = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today + timedelta(days=1),
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        result = apply_realign_scheduled_assignment_times(from_date=self.today)
        self.assertEqual(result.applied, 1)
        row.refresh_from_db()
        self.assertEqual(row.start_time, time(18, 30))
        self.assertEqual(row.end_time, time(6, 30))

    def test_skips_site_already_on_legacy_hours(self):
        legacy_site = Site.objects.create(
            name="Std",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=legacy_site,
            shift_date=self.today + timedelta(days=1),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        plan = plan_realign_scheduled_assignment_times(from_date=self.today)
        self.assertEqual(len(plan.candidates), 0)
