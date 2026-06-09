from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from shifts.models import FixedPost, ShiftAssignment
from shifts.services import ensure_assignments_for_dates
from shifts.titular_replacement import (
    dismiss_suspended_titular,
    promote_replacement_to_titular_on_dispatch,
    reinstate_suspended_titular,
    retire_titular_fixed_post,
)
from webadmin.vigile_delete import delete_vigile, release_vigile_from_active_posts

User = get_user_model()


class ReinstateConflictTests(TestCase):
    def setUp(self):
        from sites.models import Site

        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(18, 0),
            expected_end_time=time(6, 0),
            night_staff_required=2,
            latitude=1,
            longitude=1,
        )
        self.titular = User.objects.create_user(username="t1", password="x", role="vigile")
        self.replacement = User.objects.create_user(username="rep", password="x", role="vigile")
        self.post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.titular,
            is_active=True,
        )
        ensure_assignments_for_dates([self.today, self.tomorrow])

    def _dispatch(self):
        assignment = ShiftAssignment.objects.get(
            site=self.site,
            shift_date=self.today,
            start_time=time(18, 0),
            guard=self.titular,
        )
        assignment.guard_id = self.replacement.id
        assignment.status = ShiftAssignment.Status.REPLACED
        assignment.original_guard_id = self.titular.id
        assignment.save()
        promote_replacement_to_titular_on_dispatch(
            assignment,
            absent_guard_id=self.titular.id,
            replacement_guard_id=self.replacement.id,
        )
        return FixedPost.objects.get(pk=self.post.pk)

    def test_reinstate_with_duplicate_scheduled_for_reinstated_guard(self):
        post = self._dispatch()
        ShiftAssignment.objects.create(
            site=self.site,
            shift_date=self.tomorrow,
            start_time=time(18, 0),
            end_time=time(6, 0),
            guard=self.titular,
            status=ShiftAssignment.Status.SCHEDULED,
        )
        reinstate_suspended_titular(
            post,
            reason="Absence justifiee par certificat medical valide.",
        )
        post.refresh_from_db()
        self.assertEqual(post.titular_guard_id, self.titular.id)
        self.assertIsNone(post.suspended_titular_guard_id)
        self.assertEqual(
            ShiftAssignment.objects.filter(
                site=self.site,
                shift_date=self.tomorrow,
                start_time=time(18, 0),
                guard=self.titular,
                status=ShiftAssignment.Status.SCHEDULED,
            ).count(),
            1,
        )

    def test_retire_with_clear_suspended_when_dispatch_pending(self):
        post = self._dispatch()
        post, _ = retire_titular_fixed_post(
            post,
            reason="Reduction effectif nuit sur ce site.",
            clear_suspended=True,
        )
        post.refresh_from_db()
        self.assertFalse(post.is_active)
        self.assertIsNone(post.suspended_titular_guard_id)

    def test_dismiss_suspended_keeps_interim_titular(self):
        post = self._dispatch()
        dismiss_suspended_titular(
            post,
            reason="Mutation definitive ancien titulaire sur autre site.",
        )
        post.refresh_from_db()
        self.assertEqual(post.titular_guard_id, self.replacement.id)
        self.assertIsNone(post.suspended_titular_guard_id)


class VigileForceDeleteTests(TestCase):
    def setUp(self):
        from sites.models import Site

        self.site = Site.objects.create(
            name="Del",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.guard = User.objects.create_user(username="del_g", password="x", role="vigile")
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard,
            is_active=True,
        )

    def test_release_and_delete_titular(self):
        pk = self.guard.pk
        delete_vigile(self.guard, force_release=True)
        self.assertFalse(User.objects.filter(pk=pk).exists())
        self.assertFalse(FixedPost.objects.filter(titular_guard_id=pk, is_active=True).exists())

    def test_release_vigile_from_suspended_post(self):
        other = User.objects.create_user(username="other", password="x", role="vigile")
        interim = User.objects.create_user(username="interim", password="x", role="vigile")
        post = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=interim,
            suspended_titular_guard=other,
            is_active=True,
        )
        release_vigile_from_active_posts(other)
        post.refresh_from_db()
        self.assertIsNone(post.suspended_titular_guard_id)
        self.assertTrue(post.is_active)
