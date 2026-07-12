from datetime import date, time

from django.test import TestCase

from accounts.models import User
from checkins.models import Checkin
from checkins.open_shift_cleanup import (
    auto_close_stale_open_assignments_before_start,
    stale_open_assignments_for_guard,
)
from shifts.models import ShiftAssignment
from sites.models import Site


class StaleOpenShiftCleanupTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="VIR-DAY", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site Jour",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.yesterday = date(2026, 7, 10)
        self.today = date(2026, 7, 11)
        self.old_open = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.yesterday,
            start_time=time(6, 30),
            end_time=time(18, 30),
        )
        Checkin.objects.create(
            guard=self.guard,
            assignment=self.old_open,
            type=Checkin.Type.START,
            latitude=1,
            longitude=1,
        )
        self.today_assignment = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today,
            start_time=time(6, 30),
            end_time=time(18, 30),
        )

    def test_stale_open_detected_before_today(self):
        rows = list(
            stale_open_assignments_for_guard(
                self.guard.pk,
                before_shift_date=self.today,
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pk, self.old_open.pk)

    def test_auto_close_on_new_start(self):
        closed = auto_close_stale_open_assignments_before_start(
            self.guard.pk,
            self.today_assignment,
            actor=self.guard,
        )
        self.assertEqual(closed, [self.old_open.pk])
        self.assertTrue(
            Checkin.objects.filter(assignment=self.old_open, type=Checkin.Type.END).exists()
        )
        self.old_open.refresh_from_db()
        self.assertEqual(self.old_open.status, ShiftAssignment.Status.COMPLETED)

    def test_same_day_open_not_closed_when_starting_second_slot(self):
        """Jour + nuit même date : démarrer la nuit ne clôture pas le jour ouvert."""
        night = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today,
            start_time=time(18, 30),
            end_time=time(6, 30),
        )
        closed = auto_close_stale_open_assignments_before_start(
            self.guard.pk,
            night,
            actor=self.guard,
        )
        self.assertEqual(closed, [self.old_open.pk])
        self.assertFalse(
            Checkin.objects.filter(assignment=night, type=Checkin.Type.END).exists()
        )
