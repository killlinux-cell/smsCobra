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
