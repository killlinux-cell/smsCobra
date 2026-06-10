from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site
from webadmin.vigile_placement import build_vigile_placement

User = get_user_model()


class VigilePlacementTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(
            username="v1",
            password="x",
            role=User.Role.VIGILE,
            first_name="Jean",
            last_name="Dupont",
        )
        self.site = Site.objects.create(
            name="TREICHVILLE",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )

    def test_titular_is_posted(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard,
            is_active=True,
        )
        data = build_vigile_placement(self.guard)
        self.assertTrue(data["is_posted"])
        self.assertEqual(data["placements"][0]["site_name"], "TREICHVILLE")
        self.assertEqual(data["placements"][0]["role"], "Titulaire en poste")

    def test_unposted_shows_empty(self):
        data = build_vigile_placement(self.guard)
        self.assertFalse(data["is_posted"])
        self.assertEqual(len(data["placements"]), 0)

    def test_today_assignment_without_fixed_post(self):
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        data = build_vigile_placement(self.guard)
        self.assertTrue(data["is_posted"])
        self.assertIn("aujourd'hui", data["placements"][0]["role"].lower())

    def test_completed_today_not_shown_as_posted(self):
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.COMPLETED,
        )
        data = build_vigile_placement(self.guard)
        self.assertFalse(data["is_posted"])
        self.assertEqual(len(data["placements"]), 0)

    def test_extra_today_shows_extra_role(self):
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=timezone.localdate(),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.EXTRA,
        )
        data = build_vigile_placement(self.guard)
        self.assertTrue(data["is_posted"])
        self.assertEqual(data["placements"][0]["role"], "Extra")

    def test_designated_replacement_shown(self):
        other = User.objects.create_user(
            username="v2",
            password="x",
            role=User.Role.VIGILE,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=other,
            replacement_guard=self.guard,
            replacement_active=False,
            is_active=True,
        )
        data = build_vigile_placement(self.guard)
        self.assertTrue(data["is_posted"])
        self.assertEqual(data["placements"][0]["role"], "Remplaçant désigné")

    def test_same_site_day_and_night_counts_one_site_in_banner(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard,
            is_active=True,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard,
            is_active=True,
        )
        data = build_vigile_placement(self.guard)
        self.assertEqual(len(data["placements"]), 2)
        self.assertEqual(data["distinct_site_count"], 1)
        self.assertEqual(data["distinct_sites"][0]["site_name"], "TREICHVILLE")

    def test_two_sites_counted_separately(self):
        site_b = Site.objects.create(
            name="PLATEAU",
            address="B",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=2,
            longitude=2,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard,
            is_active=True,
        )
        FixedPost.objects.create(
            site=site_b,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard,
            is_active=True,
        )
        data = build_vigile_placement(self.guard)
        self.assertEqual(data["distinct_site_count"], 2)
        names = {s["site_name"] for s in data["distinct_sites"]}
        self.assertEqual(names, {"TREICHVILLE", "PLATEAU"})
