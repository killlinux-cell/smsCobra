from datetime import date, time

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase

from sites.models import Site
from shifts.models import FixedPost, ShiftAssignment
from shifts.services import ensure_assignments_for_dates

User = get_user_model()


class PassationWindowTests(TestCase):
    def setUp(self):
        self.guard_a = User.objects.create_user(username="ga", password="x", role="vigile")
        self.guard_b = User.objects.create_user(username="gb", password="x", role="vigile")
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(19, 0),
            latitude=1,
            longitude=1,
            morning_passation_start=time(6, 0),
            morning_passation_end=time(7, 0),
            evening_passation_start=time(18, 0),
            evening_passation_end=time(19, 0),
        )

    def test_relief_in_morning_window_ok(self):
        d = date.today()
        incoming = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=self.site,
            shift_date=d,
            start_time=time(6, 30),
            end_time=time(18, 0),
        )
        ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=self.site,
            shift_date=d,
            start_time=time(18, 0),
            end_time=time(6, 30),
            relieved_by=incoming,
        )

    def test_relief_outside_windows_rejected(self):
        d = date.today()
        incoming = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=self.site,
            shift_date=d,
            start_time=time(10, 0),
            end_time=time(18, 0),
        )
        with self.assertRaises(ValidationError):
            ShiftAssignment.objects.create(
                guard=self.guard_a,
                site=self.site,
                shift_date=d,
                start_time=time(18, 0),
                end_time=time(10, 0),
                relieved_by=incoming,
            )


class FixedPostMaterializationTests(TestCase):
    def setUp(self):
        self.guard_a = User.objects.create_user(username="gfa", password="x", role="vigile")
        self.guard_b = User.objects.create_user(username="gfb", password="x", role="vigile")
        self.site = Site.objects.create(
            name="S2",
            address="A2",
            expected_start_time=time(6, 0),
            expected_end_time=time(19, 0),
            latitude=1,
            longitude=1,
        )

    def test_fixed_post_generates_daily_assignment(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard_a,
            is_active=True,
        )
        d = date.today()
        ensure_assignments_for_dates([d])
        a = ShiftAssignment.objects.filter(site=self.site, shift_date=d, start_time=time(6, 0)).first()
        self.assertIsNotNone(a)
        self.assertEqual(a.guard_id, self.guard_a.id)
        self.assertEqual(a.status, ShiftAssignment.Status.SCHEDULED)

    def test_fixed_post_uses_active_replacement(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard_a,
            replacement_guard=self.guard_b,
            replacement_active=True,
            is_active=True,
        )
        d = date.today()
        ensure_assignments_for_dates([d])
        a = ShiftAssignment.objects.filter(site=self.site, shift_date=d, start_time=time(18, 0)).first()
        self.assertIsNotNone(a)
        self.assertEqual(a.guard_id, self.guard_b.id)
        self.assertEqual(a.original_guard_id, self.guard_a.id)
        self.assertEqual(a.status, ShiftAssignment.Status.REPLACED)
