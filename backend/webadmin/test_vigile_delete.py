from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shifts.models import FixedPost
from sites.models import Site
from webadmin.vigile_delete import delete_vigile, get_vigile_delete_context

User = get_user_model()


class VigileDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_d",
            password="x",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.guard = User.objects.create_user(
            username="v_del",
            password="x",
            role=User.Role.VIGILE,
        )
        self.site = Site.objects.create(
            name="S",
            address="A",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )

    def test_can_delete_unposted_vigile(self):
        ctx = get_vigile_delete_context(self.guard)
        self.assertTrue(ctx["can_delete"])

    def test_blocks_active_titular(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.DAY,
            titular_guard=self.guard,
            is_active=True,
        )
        ctx = get_vigile_delete_context(self.guard)
        self.assertFalse(ctx["can_delete"])
        self.assertTrue(ctx["blockers"])

    def test_delete_removes_user(self):
        pk = self.guard.pk
        delete_vigile(self.guard)
        self.assertFalse(User.objects.filter(pk=pk).exists())

    def test_delete_view_requires_login(self):
        url = reverse("webadmin-vigile-delete", args=[self.guard.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
