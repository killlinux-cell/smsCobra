from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.roulement_convert import convert_vigile_to_roulement
from accounts.roulement_username import generate_roulement_username, is_standard_roulement_username
from shifts.models import FixedPost, ShiftAssignment
from shifts.roulement_assignment import create_roulement_assignments
from shifts.titular_replacement import promote_replacement_to_titular_on_dispatch
from sites.models import Site

User = get_user_model()


class RoulementUsernameTests(TestCase):
    def test_generate_rlt_username(self):
        User.objects.create_user(username="RLT-001", password="x", role="vigile", is_roulement=True)
        self.assertEqual(generate_roulement_username(), "RLT-002")
        self.assertTrue(is_standard_roulement_username("RLT-002"))


class RoulementAssignmentTests(TestCase):
    def setUp(self):
        self.rlt = User.objects.create_user(
            username="RLT-010",
            password="x",
            role="vigile",
            is_roulement=True,
        )
        self.site_a = Site.objects.create(
            name="Site A",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            day_staff_required=2,
            night_staff_required=1,
            latitude=1,
            longitude=1,
        )
        self.site_b = Site.objects.create(
            name="Site B",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(20, 0),
            day_staff_required=1,
            night_staff_required=1,
            latitude=1,
            longitude=1,
        )
        self.day = date(2026, 8, 10)

    def test_create_roulement_uses_site_hours(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site_b,
            shift_date=self.day,
            shift_type="day",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].start_time, time(8, 0))
        self.assertEqual(rows[0].end_time, time(20, 0))
        self.assertEqual(rows[0].status, ShiftAssignment.Status.ROULEMENT)

    def test_rlt_can_cover_two_sites_same_day_different_hours(self):
        create_roulement_assignments(
            guard=self.rlt,
            site=self.site_a,
            shift_date=self.day,
            shift_type="day",
        )
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site_b,
            shift_date=self.day,
            shift_type="day",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            ShiftAssignment.objects.filter(
                guard=self.rlt,
                shift_date=self.day,
                status=ShiftAssignment.Status.ROULEMENT,
            ).count(),
            2,
        )

    def test_multi_day_roulement(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site_a,
            shift_date=self.day,
            shift_type="day",
            roulement_days=6,
        )
        self.assertEqual(len(rows), 6)


class ConvertToRoulementTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.vigile = User.objects.create_user(username="VIR-050", password="x", role="vigile")
        self.post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.vigile,
            is_active=True,
        )

    def test_convert_releases_fixed_post(self):
        convert_vigile_to_roulement(self.vigile)
        self.vigile.refresh_from_db()
        self.post.refresh_from_db()
        self.assertTrue(self.vigile.is_roulement)
        self.assertTrue(self.vigile.username.startswith("RLT-"))
        self.assertFalse(self.post.is_active)


class RoulementNoTitularPromotionTests(TestCase):
    def setUp(self):
        self.titular = User.objects.create_user(username="VIR-T", password="x", role="vigile")
        self.rlt = User.objects.create_user(
            username="RLT-099",
            password="x",
            role="vigile",
            is_roulement=True,
        )
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.titular,
            is_active=True,
        )
        self.today = timezone.localdate()
        self.assignment = ShiftAssignment.objects.create(
            guard=self.titular,
            site=self.site,
            shift_date=self.today,
            start_time=time(6, 0),
            end_time=time(18, 0),
        )

    def test_dispatch_does_not_promote_roulement(self):
        post = promote_replacement_to_titular_on_dispatch(
            self.assignment,
            absent_guard_id=self.titular.id,
            replacement_guard_id=self.rlt.id,
        )
        self.assertIsNone(post)
        self.post.refresh_from_db()
        self.assertEqual(self.post.titular_guard_id, self.titular.id)
