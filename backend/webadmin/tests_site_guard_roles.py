from datetime import date, time

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site
from webadmin.site_guard_roles import (
    enrich_guard_roles_from_assignments,
    sort_role_labels,
)


class SiteGuardRolesTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.site = Site.objects.create(
            name="Site Test",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        self.titular = User.objects.create_user(
            username="TIT-001",
            password="x",
            role=User.Role.VIGILE,
        )
        self.dispatch = User.objects.create_user(
            username="DEP-001",
            password="x",
            role=User.Role.VIGILE,
        )
        self.fixed = FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.titular,
            is_active=True,
        )
        self.roles: dict[int, set[str]] = {}

        def note_role(user, label: str) -> None:
            self.roles.setdefault(user.id, set()).add(label)

        self.note_role = note_role

    def _enrich(self, assignments):
        enrich_guard_roles_from_assignments(
            [self.fixed],
            assignments,
            today=self.today,
            note_role=self.note_role,
        )

    def test_dispatch_guard_gets_role_without_fixed_post(self):
        ShiftAssignment.objects.create(
            guard=self.dispatch,
            site=self.site,
            shift_date=self.today,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.REPLACED,
            original_guard=self.titular,
        )
        self._enrich(ShiftAssignment.objects.filter(site=self.site))
        self.assertIn("Dépêche — nuit", self.roles[self.dispatch.id])
        self.assertNotIn(self.titular.id, self.roles)

    def test_extra_guard_gets_extra_role(self):
        extra = User.objects.create_user(
            username="EXT-001",
            password="x",
            role=User.Role.VIGILE,
        )
        ShiftAssignment.objects.create(
            guard=extra,
            site=self.site,
            shift_date=self.today,
            start_time=time(6, 0),
            end_time=time(18, 0),
            status=ShiftAssignment.Status.EXTRA,
        )
        self._enrich(ShiftAssignment.objects.filter(site=self.site))
        self.assertIn("Extra — jour", self.roles[extra.id])

    def test_sort_role_labels_puts_titulaire_first(self):
        ordered = sort_role_labels(
            [
                "Dépêche — nuit",
                "Titulaire — jour",
                "En poste aujourd'hui — nuit",
            ]
        )
        self.assertEqual(ordered[0], "Titulaire — jour")
        self.assertEqual(ordered[1], "Dépêche — nuit")
