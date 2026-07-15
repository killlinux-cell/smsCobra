from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase

from shifts.models import FixedPost, ShiftAssignment
from shifts.slot_occupancy import (
    count_occupying_assignments,
    has_blocking_assignment_for_new_titular,
    purge_all_sites_orphaned_scheduled,
    purge_orphaned_scheduled_for_slot,
)
from sites.models import Site

User = get_user_model()


class SlotOccupancyTests(TestCase):
    def setUp(self):
        self.guard_old = User.objects.create_user(username="old_n", password="x", role="vigile")
        self.guard_new = User.objects.create_user(username="new_n", password="x", role="vigile")
        self.site = Site.objects.create(
            name="King",
            address="Abidjan",
            day_staff_required=1,
            night_staff_required=1,
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.day = date(2026, 6, 16)

    def test_orphan_scheduled_does_not_block_vacant_night_slot(self):
        ShiftAssignment.objects.create(
            guard=self.guard_old,
            site=self.site,
            shift_date=self.day,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard_new,
            is_active=True,
        )
        count = count_occupying_assignments(
            site_id=self.site.pk,
            shift_date=self.day,
            start_time=time(18, 0),
            shift_type=FixedPost.ShiftType.NIGHT,
        )
        self.assertEqual(count, 0)

    def test_purge_orphaned_scheduled_when_no_active_night_post(self):
        ShiftAssignment.objects.create(
            guard=self.guard_old,
            site=self.site,
            shift_date=self.day,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        deleted = purge_orphaned_scheduled_for_slot(
            site_id=self.site.pk,
            shift_type=FixedPost.ShiftType.NIGHT,
            from_date=self.day,
        )
        self.assertEqual(deleted, 1)
        self.assertFalse(
            ShiftAssignment.objects.filter(
                site=self.site,
                start_time=time(18, 0),
                guard=self.guard_old,
            ).exists()
        )

    def test_second_night_titular_not_blocked_when_one_slot_taken(self):
        self.site.night_staff_required = 2
        self.site.save(update_fields=["night_staff_required"])
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard_old,
            is_active=True,
        )
        ShiftAssignment.objects.create(
            guard=self.guard_old,
            site=self.site,
            shift_date=self.day,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        self.assertFalse(
            has_blocking_assignment_for_new_titular(
                site_id=self.site.pk,
                shift_date=self.day,
                start_time=time(18, 0),
                shift_type=FixedPost.ShiftType.NIGHT,
                guard_id=self.guard_new.pk,
            )
        )

    def test_orphan_scheduled_does_not_block_same_guard_reassignment(self):
        ShiftAssignment.objects.create(
            guard=self.guard_old,
            site=self.site,
            shift_date=self.day,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )
        self.assertFalse(
            has_blocking_assignment_for_new_titular(
                site_id=self.site.pk,
                shift_date=self.day,
                start_time=time(18, 0),
                shift_type=FixedPost.ShiftType.NIGHT,
                guard_id=self.guard_old.pk,
            )
        )

    def test_purge_all_sites_orphaned_scheduled(self):
        site2 = Site.objects.create(
            name="Other",
            address="Abidjan",
            day_staff_required=1,
            night_staff_required=1,
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        for site in (self.site, site2):
            ShiftAssignment.objects.create(
                guard=self.guard_old,
                site=site,
                shift_date=self.day,
                start_time=time(18, 0),
                end_time=time(6, 0),
                status=ShiftAssignment.Status.SCHEDULED,
            )
        deleted = purge_all_sites_orphaned_scheduled(from_date=self.day)
        self.assertEqual(deleted, 2)
        self.assertFalse(ShiftAssignment.objects.filter(status=ShiftAssignment.Status.SCHEDULED).exists())
