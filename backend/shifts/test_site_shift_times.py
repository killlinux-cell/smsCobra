from datetime import date, time

from django.test import TestCase

from shifts.models import FixedPost
from shifts.site_shift_times import (
    day_slot_times,
    incoming_relief_lookup,
    night_slot_times,
    shift_type_for_start_time,
    slot_times_for_site,
)
from sites.models import Site


class SiteShiftTimesTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="King Deco",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )

    def test_day_slot_uses_site_expected_times(self):
        self.assertEqual(day_slot_times(self.site), (time(6, 30), time(18, 30)))

    def test_night_slot_uses_site_end_as_start(self):
        self.assertEqual(night_slot_times(self.site), (time(18, 30), time(6, 30)))

    def test_slot_times_for_site_day_and_night(self):
        self.assertEqual(
            slot_times_for_site(self.site, FixedPost.ShiftType.DAY),
            (time(6, 30), time(18, 30)),
        )
        self.assertEqual(
            slot_times_for_site(self.site, FixedPost.ShiftType.NIGHT),
            (time(18, 30), time(6, 30)),
        )

    def test_shift_type_detection(self):
        self.assertEqual(
            shift_type_for_start_time(self.site, time(6, 30)),
            FixedPost.ShiftType.DAY,
        )
        self.assertEqual(
            shift_type_for_start_time(self.site, time(18, 30)),
            FixedPost.ShiftType.NIGHT,
        )

    def test_incoming_relief_for_day_shift(self):
        d = date(2026, 6, 16)
        self.assertEqual(
            incoming_relief_lookup(self.site, FixedPost.ShiftType.DAY, d),
            (d, time(18, 30)),
        )

    def test_incoming_relief_for_night_shift(self):
        d = date(2026, 6, 16)
        self.assertEqual(
            incoming_relief_lookup(self.site, FixedPost.ShiftType.NIGHT, d),
            (date(2026, 6, 17), time(6, 30)),
        )


class NightOnlyInvertedSiteShiftTimesTests(TestCase):
    """Sites 0 jour / 1 nuit avec horaires 19h→7h (ex. GILL LANDY)."""

    def setUp(self):
        self.site = Site.objects.create(
            name="GILL LANDY",
            address="MBADON",
            expected_start_time=time(19, 0),
            expected_end_time=time(7, 0),
            day_staff_required=0,
            night_staff_required=1,
            latitude=1,
            longitude=1,
        )

    def test_night_only_inverted_site_maps_night_post_to_expected_hours(self):
        self.assertEqual(
            slot_times_for_site(self.site, FixedPost.ShiftType.NIGHT),
            (time(19, 0), time(7, 0)),
        )

    def test_night_only_inverted_start_at_19_is_night_not_day(self):
        self.assertEqual(
            shift_type_for_start_time(self.site, time(19, 0)),
            FixedPost.ShiftType.NIGHT,
        )
        self.assertIsNone(shift_type_for_start_time(self.site, time(7, 0)))

    def test_morning_spurious_07_assignment_not_operational(self):
        from django.contrib.auth import get_user_model

        from shifts.models import ShiftAssignment
        from shifts.site_shift_times import assignment_is_operational

        User = get_user_model()
        guard = User.objects.create_user(username="night_g", password="x", role="vigile")
        wrong = ShiftAssignment.objects.create(
            guard=guard,
            site=self.site,
            shift_date=date(2026, 6, 16),
            start_time=time(7, 0),
            end_time=time(19, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        correct = ShiftAssignment.objects.create(
            guard=guard,
            site=self.site,
            shift_date=date(2026, 6, 16),
            start_time=time(19, 0),
            end_time=time(7, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        self.assertFalse(assignment_is_operational(wrong))
        self.assertTrue(assignment_is_operational(correct))
