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
        self.day = date(2026, 8, 10)
        self.rlt = User.objects.create_user(
            username="RLT-010",
            password="x",
            role="vigile",
            is_roulement=True,
            roulement_cycle_anchor=self.day,
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
        self.titular_a = User.objects.create_user(username="VIR-A1", password="x", role="vigile")
        self.titular_b = User.objects.create_user(username="VIR-B1", password="x", role="vigile")
        FixedPost.objects.create(
            site=self.site_a,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.titular_a,
            is_active=True,
        )
        FixedPost.objects.create(
            site=self.site_b,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.titular_b,
            is_active=True,
        )

    def test_create_roulement_uses_site_hours(self):
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site_b,
            shift_date=self.day,
            shift_type="day",
            relieved_titular=self.titular_b,
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
            relieved_titular=self.titular_a,
        )
        rows = create_roulement_assignments(
            guard=self.rlt,
            site=self.site_b,
            shift_date=self.day,
            shift_type="day",
            relieved_titular=self.titular_b,
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
            relieved_titular=self.titular_a,
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
        self.titular = User.objects.create_user(username="VIR-051", password="x", role="vigile")
        self.post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.titular,
            is_active=True,
        )

    def test_convert_non_titular(self):
        convert_vigile_to_roulement(self.vigile)
        self.vigile.refresh_from_db()
        self.assertTrue(self.vigile.is_roulement)
        self.assertTrue(self.vigile.username.startswith("RLT-"))

    def test_convert_titular_rejected(self):
        with self.assertRaises(ValidationError):
            convert_vigile_to_roulement(self.titular)
        self.titular.refresh_from_db()
        self.assertFalse(self.titular.is_roulement)

    def test_convert_rlt_back_to_vigile(self):
        from accounts.roulement_convert import convert_roulement_to_vigile
        from reports.models import RoulementChangeLog

        convert_vigile_to_roulement(self.vigile)
        self.vigile.refresh_from_db()
        rlt_username = self.vigile.username
        restored = convert_roulement_to_vigile(self.vigile)
        restored.refresh_from_db()
        self.assertFalse(restored.is_roulement)
        self.assertTrue(restored.username.startswith("VIR-"))
        self.assertNotEqual(restored.username, rlt_username)
        self.assertIsNone(restored.roulement_cycle_anchor)
        self.assertTrue(
            RoulementChangeLog.objects.filter(
                kind=RoulementChangeLog.Kind.RESTORED, rlt_guard=restored
            ).exists()
        )

    def test_convert_rlt_cancels_future_missions(self):
        from accounts.roulement_convert import convert_roulement_to_vigile
        from django.utils import timezone
        from shifts.roulement_assignment import create_roulement_assignments

        convert_vigile_to_roulement(self.vigile)
        self.vigile.refresh_from_db()
        day = timezone.localdate()
        self.site.day_staff_required = 1
        self.site.save(update_fields=["day_staff_required"])
        create_roulement_assignments(
            guard=self.vigile,
            site=self.site,
            shift_date=day,
            shift_type="day",
            relieved_titular=self.titular,
        )
        convert_roulement_to_vigile(self.vigile)
        self.assertFalse(
            ShiftAssignment.objects.filter(
                guard=self.vigile, status=ShiftAssignment.Status.ROULEMENT
            ).exists()
        )
        titular_asg = ShiftAssignment.objects.get(
            guard=self.titular, site=self.site, shift_date=day
        )
        self.assertEqual(titular_asg.status, ShiftAssignment.Status.SCHEDULED)


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


class RoulementAssignmentFormTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate()
        self.rlt = User.objects.create_user(
            username="RLT-010",
            password="x",
            role="vigile",
            is_roulement=True,
            first_name="Jean",
            last_name="Bogui",
            roulement_cycle_anchor=self.day,
        )
        self.site = Site.objects.create(
            name="Impérial",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(20, 0),
            day_staff_required=0,
            night_staff_required=1,
            latitude=1,
            longitude=1,
        )
        self.tido = User.objects.create_user(
            username="VIR-143",
            password="x",
            role="vigile",
            first_name="Tido",
            last_name="Test",
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.tido,
            is_active=True,
        )

    def test_form_accepts_relieved_titular_on_post(self):
        from webadmin.forms import RoulementAssignmentForm

        form = RoulementAssignmentForm(
            data={
                "guard": str(self.rlt.pk),
                "site": str(self.site.pk),
                "shift_date": self.day.isoformat(),
                "shift_type": "night",
                "roulement_days": "1",
                "relieved_titular": str(self.tido.pk),
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
        rows = form.save()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].original_guard_id, self.tido.pk)

    def test_form_rejects_day_shift_when_site_has_no_day_post(self):
        from webadmin.forms import RoulementAssignmentForm

        form = RoulementAssignmentForm(
            data={
                "guard": str(self.rlt.pk),
                "site": str(self.site.pk),
                "shift_date": self.day.isoformat(),
                "shift_type": "day",
                "roulement_days": "1",
                "relieved_titular": str(self.tido.pk),
            }
        )
        self.assertFalse(form.is_valid())
