from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from accounts.models import User
from shifts.assignment_pick import pick_assignment_for_guard
from shifts.models import ShiftAssignment
from sites.models import Site


class AssignmentPickTests(TestCase):
    def setUp(self):
        self.site_a = Site.objects.create(
            name="Site A",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        self.site_b = Site.objects.create(
            name="Site B",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.35,
            longitude=-4.03,
        )
        self.guard = User.objects.create_user(
            username="VIR-PICK",
            password="x",
            role=User.Role.VIGILE,
        )
        self.other = User.objects.create_user(
            username="VIR-OTHER",
            password="x",
            role=User.Role.VIGILE,
        )

    def test_pick_returns_identified_guard_assignment_only(self):
        mine = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site_a,
            shift_date=date.today(),
            start_time=time(8, 0),
            end_time=time(17, 0),
        )
        ShiftAssignment.objects.create(
            guard=self.other,
            site=self.site_a,
            shift_date=date.today(),
            start_time=time(8, 0),
            end_time=time(17, 0),
        )
        picked = pick_assignment_for_guard(self.guard.id)
        self.assertEqual(picked.id, mine.id)

    @patch("shifts.assignment_pick.timezone.now")
    def test_without_site_picks_active_among_guard_sites(self, mock_now):
        tz = timezone.get_current_timezone()
        mock_now.return_value = timezone.make_aware(
            datetime(2026, 6, 9, 10, 0), tz
        )
        morning = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site_a,
            shift_date=date(2026, 6, 9),
            start_time=time(6, 0),
            end_time=time(14, 0),
        )
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site_b,
            shift_date=date(2026, 6, 9),
            start_time=time(14, 0),
            end_time=time(22, 0),
        )
        picked = pick_assignment_for_guard(self.guard.id, now=mock_now.return_value)
        self.assertEqual(picked.id, morning.id)
