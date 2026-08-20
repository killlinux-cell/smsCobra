from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from shifts.roulement_assignment import create_roulement_assignments
from shifts.roulement_cycle import (
    build_guard_calendar,
    cycle_position,
    is_rest_day,
    validate_service_days,
)
from sites.models import Site

User = get_user_model()


class RoulementCycleTests(TestCase):
    def setUp(self):
        self.anchor = date(2026, 8, 10)
        self.rlt = User.objects.create_user(
            username="RLT-020",
            password="x",
            role="vigile",
            is_roulement=True,
            roulement_cycle_anchor=self.anchor,
        )
        self.site = Site.objects.create(
            name="Site A",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            day_staff_required=1,
            night_staff_required=1,
            latitude=1,
            longitude=1,
        )

    def test_cycle_position(self):
        self.assertEqual(cycle_position(self.anchor, self.anchor), 0)
        self.assertEqual(cycle_position(self.anchor + timedelta(days=5), self.anchor), 5)
        self.assertTrue(is_rest_day(self.anchor + timedelta(days=6), self.anchor))
        self.assertFalse(is_rest_day(self.anchor + timedelta(days=7), self.anchor))

    def test_reject_assignment_on_rest_day(self):
        rest_day = self.anchor + timedelta(days=6)
        with self.assertRaises(ValidationError):
            validate_service_days(guard=self.rlt, shift_date=rest_day, roulement_days=1)

    def test_reject_multi_day_spanning_rest(self):
        with self.assertRaises(ValidationError):
            validate_service_days(
                guard=self.rlt,
                shift_date=self.anchor + timedelta(days=4),
                roulement_days=3,
            )

    def test_calendar_marks_rest_and_mission(self):
        service_day = self.anchor + timedelta(days=1)
        create_roulement_assignments(
            guard=self.rlt,
            site=self.site,
            shift_date=service_day,
            shift_type="day",
        )
        days = build_guard_calendar(self.rlt, start=self.anchor, days=8)
        by_date = {d["date"]: d for d in days}
        self.assertEqual(by_date[self.anchor + timedelta(days=6)]["status"], "rest")
        self.assertEqual(by_date[service_day]["status"], "mission")
