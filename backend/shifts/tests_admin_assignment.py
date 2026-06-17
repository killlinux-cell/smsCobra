from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site


class AdminAssignmentAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ADM-PLAN",
            password="secret123",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.vigile = User.objects.create_user(
            username="VIR-PLAN",
            password="x",
            role=User.Role.VIGILE,
        )
        self.vigile_b = User.objects.create_user(
            username="VIR-PLAN2",
            password="x",
            role=User.Role.VIGILE,
        )
        self.site = Site.objects.create(
            name="Site Plan",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.35,
            longitude=-4.03,
            site_manager_phone="+2250700000000",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.today = date.today()

    def test_create_planned_assignment(self):
        resp = self.client.post(
            "/api/v1/admin/assignments/",
            {
                "planning_mode": "planifier",
                "guard": self.vigile.pk,
                "site": self.site.pk,
                "shift_date": self.today.isoformat(),
                "shift_type": "day",
                "create_fixed_post": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        row = ShiftAssignment.objects.get(
            guard=self.vigile,
            site=self.site,
            shift_date=self.today,
            status=ShiftAssignment.Status.SCHEDULED,
        )
        self.assertEqual(row.start_time, time(8, 0))
        self.assertEqual(row.end_time, time(17, 0))

    def test_create_extra_requires_titular(self):
        resp = self.client.post(
            "/api/v1/admin/assignments/",
            {
                "planning_mode": "extra",
                "extra_days": 2,
                "guard": self.vigile_b.pk,
                "site": self.site.pk,
                "shift_date": self.today.isoformat(),
                "shift_type": "day",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_extra_with_titular(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.vigile,
            is_active=True,
            start_date=self.today,
        )
        resp = self.client.post(
            "/api/v1/admin/assignments/",
            {
                "planning_mode": "extra",
                "extra_days": 2,
                "guard": self.vigile_b.pk,
                "site": self.site.pk,
                "shift_date": self.today.isoformat(),
                "shift_type": "day",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            ShiftAssignment.objects.filter(
                guard=self.vigile_b,
                site=self.site,
                status=ShiftAssignment.Status.EXTRA,
            ).count(),
            2,
        )

    def test_list_assignments(self):
        ShiftAssignment.objects.create(
            guard=self.vigile,
            site=self.site,
            shift_date=self.today,
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        resp = self.client.get("/api/v1/admin/assignments/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)
