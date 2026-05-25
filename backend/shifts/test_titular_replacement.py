from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from sites.models import Site
from shifts.models import FixedPost, ShiftAssignment
from shifts.services import ensure_assignments_for_dates
from shifts.titular_replacement import (
    promote_replacement_to_titular_on_dispatch,
    reinstate_suspended_titular,
)

User = get_user_model()


class TitularPromotionTests(TestCase):
    def setUp(self):
        self.titular = User.objects.create_user(username="tit", password="x", role="vigile")
        self.replacement = User.objects.create_user(username="rep", password="x", role="vigile")
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
        ensure_assignments_for_dates([self.today, self.today + timedelta(days=1)])

    def test_dispatch_promotes_replacement_to_titular(self):
        assignment = ShiftAssignment.objects.get(
            site=self.site, shift_date=self.today, start_time=time(6, 0)
        )
        self.assertEqual(assignment.guard_id, self.titular.id)

        assignment.guard_id = self.replacement.id
        assignment.status = ShiftAssignment.Status.REPLACED
        assignment.original_guard_id = self.titular.id
        assignment.save()

        post = promote_replacement_to_titular_on_dispatch(
            assignment,
            absent_guard_id=self.titular.id,
            replacement_guard_id=self.replacement.id,
        )
        self.assertIsNotNone(post)
        post.refresh_from_db()
        self.assertEqual(post.titular_guard_id, self.replacement.id)
        self.assertEqual(post.suspended_titular_guard_id, self.titular.id)
        self.assertFalse(post.replacement_active)

        tomorrow = ShiftAssignment.objects.get(
            site=self.site,
            shift_date=self.today + timedelta(days=1),
            start_time=time(6, 0),
        )
        self.assertEqual(tomorrow.guard_id, self.replacement.id)
        self.assertEqual(tomorrow.status, ShiftAssignment.Status.SCHEDULED)

    def test_reinstate_restores_titular(self):
        assignment = ShiftAssignment.objects.get(
            site=self.site, shift_date=self.today, start_time=time(6, 0)
        )
        promote_replacement_to_titular_on_dispatch(
            assignment,
            absent_guard_id=self.titular.id,
            replacement_guard_id=self.replacement.id,
        )
        post = FixedPost.objects.get(pk=self.post.pk)
        reinstate_suspended_titular(
            post,
            reason="Certificat médical transmis et validé par le superviseur.",
        )
        post.refresh_from_db()
        self.assertEqual(post.titular_guard_id, self.titular.id)
        self.assertIsNone(post.suspended_titular_guard_id)
        self.assertIn("Certificat", post.suspension_reason)

    def test_reinstate_requires_reason(self):
        assignment = ShiftAssignment.objects.get(
            site=self.site, shift_date=self.today, start_time=time(6, 0)
        )
        promote_replacement_to_titular_on_dispatch(
            assignment,
            absent_guard_id=self.titular.id,
            replacement_guard_id=self.replacement.id,
        )
        post = FixedPost.objects.get(pk=self.post.pk)
        with self.assertRaises(ValidationError):
            reinstate_suspended_titular(post, reason="court")
