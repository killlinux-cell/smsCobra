from datetime import date, time, timedelta

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase

from sites.models import Site
from shifts.models import FixedPost, ShiftAssignment
from shifts.site_shift_times import day_slot_times, night_slot_times
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

    def test_night_shift_relief_next_morning_ok(self):
        d = date.today()
        incoming = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=self.site,
            shift_date=d + timedelta(days=1),
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=self.site,
            shift_date=d,
            start_time=time(18, 0),
            end_time=time(6, 0),
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

    def test_custom_site_hours_accepted_as_passation(self):
        """Site 07:30–19:30 : relève à 07:30 ou 19:30 valide sans ajuster les fenêtres génériques."""
        site = Site.objects.create(
            name="Imperial",
            address="A",
            expected_start_time=time(7, 30),
            expected_end_time=time(19, 30),
            latitude=1,
            longitude=1,
        )
        d = date.today()
        incoming_morning = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=site,
            shift_date=d + timedelta(days=1),
            start_time=time(7, 30),
            end_time=time(19, 30),
        )
        ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=site,
            shift_date=d,
            start_time=time(19, 30),
            end_time=time(7, 30),
            relieved_by=incoming_morning,
        )
        incoming_evening = ShiftAssignment.objects.create(
            guard=self.guard_b,
            site=site,
            shift_date=d,
            start_time=time(19, 30),
            end_time=time(7, 30),
        )
        ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=site,
            shift_date=d,
            start_time=time(7, 30),
            end_time=time(19, 30),
            relieved_by=incoming_evening,
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
        day_start, _ = day_slot_times(self.site)
        ensure_assignments_for_dates([d])
        a = ShiftAssignment.objects.filter(
            site=self.site, shift_date=d, start_time=day_start
        ).first()
        self.assertIsNotNone(a)
        self.assertEqual(a.guard_id, self.guard_a.id)
        self.assertEqual(a.status, ShiftAssignment.Status.SCHEDULED)

    def test_day_and_night_fixed_posts_link_handover(self):
        """Jour + nuit sur le même site : liaison passation sans erreur de validation."""
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard_a,
            is_active=True,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard_b,
            is_active=True,
        )
        d = date.today()
        day_start, _ = day_slot_times(self.site)
        night_start, _ = night_slot_times(self.site)
        ensure_assignments_for_dates([d, d + timedelta(days=1)])
        day_row = ShiftAssignment.objects.get(
            site=self.site, shift_date=d, start_time=day_start
        )
        night_row = ShiftAssignment.objects.get(
            site=self.site, shift_date=d, start_time=night_start
        )
        day_next = ShiftAssignment.objects.get(
            site=self.site, shift_date=d + timedelta(days=1), start_time=day_start
        )
        self.assertEqual(day_row.relieved_by_id, night_row.id)
        self.assertEqual(night_row.relieved_by_id, day_next.id)

    def test_fixed_post_respects_start_date(self):
        start = date.today() + timedelta(days=10)
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard_a,
            is_active=True,
            start_date=start,
        )
        today = date.today()
        ensure_assignments_for_dates(
            [today + timedelta(days=i) for i in range(16)]
        )
        before = ShiftAssignment.objects.filter(
            site=self.site,
            start_time=time(6, 0),
            guard=self.guard_a,
            shift_date__lt=start,
        )
        self.assertEqual(before.count(), 0)
        on_start = ShiftAssignment.objects.filter(
            site=self.site,
            shift_date=start,
            start_time=time(6, 0),
            guard=self.guard_a,
        ).first()
        self.assertIsNotNone(on_start)

    def test_fixed_post_purges_assignments_before_start_date(self):
        start = date.today() + timedelta(days=5)
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard_a,
            is_active=True,
            start_date=start,
        )
        today = date.today()
        ShiftAssignment.objects.create(
            guard=self.guard_a,
            site=self.site,
            shift_date=today,
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        ensure_assignments_for_dates([today, start])
        self.assertFalse(
            ShiftAssignment.objects.filter(
                site=self.site,
                guard=self.guard_a,
                shift_date__lt=start,
            ).exists()
        )

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
        night_start, _ = night_slot_times(self.site)
        ensure_assignments_for_dates([d])
        a = ShiftAssignment.objects.filter(
            site=self.site, shift_date=d, start_time=night_start
        ).first()
        self.assertIsNotNone(a)
        self.assertEqual(a.guard_id, self.guard_b.id)
        self.assertEqual(a.original_guard_id, self.guard_a.id)
        self.assertEqual(a.status, ShiftAssignment.Status.REPLACED)


class ExtraAssignmentFormTests(TestCase):
    def setUp(self):
        self.titular = User.objects.create_user(username="tit", password="x", role="vigile")
        self.extra_guard = User.objects.create_user(username="ext", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site Extra",
            address="Addr",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.titular,
            is_active=True,
        )
        ShiftAssignment.objects.create(
            guard=self.titular,
            site=self.site,
            shift_date=date.today(),
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )

    def test_extra_mode_creates_consecutive_assignments(self):
        from webadmin.forms import ShiftAssignmentForm

        start = date.today()
        form = ShiftAssignmentForm(
            {
                "planning_mode": ShiftAssignmentForm.MODE_EXTRA,
                "extra_days": "3",
                "guard": str(self.extra_guard.pk),
                "site": str(self.site.pk),
                "shift_date": start.isoformat(),
                "shift_type": ShiftAssignmentForm.SHIFT_TYPE_DAY,
            },
            for_create=True,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        extras = ShiftAssignment.objects.filter(
            guard=self.extra_guard,
            site=self.site,
            status=ShiftAssignment.Status.EXTRA,
        )
        self.assertEqual(extras.count(), 3)
        dates = sorted(a.shift_date for a in extras)
        self.assertEqual(dates, [start, start + timedelta(days=1), start + timedelta(days=2)])

    def test_extra_requires_titular_on_site(self):
        from webadmin.forms import ShiftAssignmentForm

        site2 = Site.objects.create(
            name="Sans titulaire",
            address="X",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        form = ShiftAssignmentForm(
            {
                "planning_mode": ShiftAssignmentForm.MODE_EXTRA,
                "extra_days": "2",
                "guard": str(self.extra_guard.pk),
                "site": str(site2.pk),
                "shift_date": date.today().isoformat(),
                "shift_type": ShiftAssignmentForm.SHIFT_TYPE_DAY,
            },
            for_create=True,
        )
        self.assertFalse(form.is_valid())


class GuardCrossSiteConflictTests(TestCase):
    def setUp(self):
        self.guard = User.objects.create_user(username="g1", password="x", role="vigile")
        self.site_a = Site.objects.create(
            name="Site Alpha",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.site_b = Site.objects.create(
            name="Site Beta",
            address="B",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=2,
            longitude=2,
        )
        self.day = date.today()

    def test_cannot_planify_same_guard_on_two_sites_same_slot(self):
        from webadmin.forms import ShiftAssignmentForm

        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site_a,
            shift_date=self.day,
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        form = ShiftAssignmentForm(
            {
                "planning_mode": ShiftAssignmentForm.MODE_PLANIFIER,
                "guard": str(self.guard.pk),
                "site": str(self.site_b.pk),
                "shift_date": self.day.isoformat(),
                "shift_type": ShiftAssignmentForm.SHIFT_TYPE_DAY,
                "create_fixed_post": "on",
            },
            for_create=True,
        )
        self.assertFalse(form.is_valid())
        err = str(form.non_field_errors())
        self.assertIn("Site Alpha", err)
        self.assertIn("déjà affecté", err)

    def test_dispatch_replacement_blocked_if_guard_busy_elsewhere(self):
        from webadmin.forms import DispatchForm

        assignment_b = ShiftAssignment.objects.create(
            guard=User.objects.create_user(username="g2", password="x", role="vigile"),
            site=self.site_b,
            shift_date=self.day,
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site_a,
            shift_date=self.day,
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        form = DispatchForm(
            {
                "assignment": str(assignment_b.pk),
                "replacement_guard": str(self.guard.pk),
            },
            assignments_qs=ShiftAssignment.objects.filter(pk=assignment_b.pk),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Site Alpha", str(form.errors))
