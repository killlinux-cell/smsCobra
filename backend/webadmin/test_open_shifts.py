from datetime import time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from checkins.models import Checkin
from shifts.models import ShiftAssignment
from sites.models import Site
from webadmin.admin_force_end import ForceEndError, supervisor_force_end_assignment
from webadmin.open_shifts import collect_open_shift_rows, count_stale_open_shifts


class OpenShiftsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_o",
            password="secret123",
            role="admin_societe",
            is_staff=True,
        )
        self.guard = User.objects.create_user(
            username="VIR-T",
            password="x",
            role="vigile",
        )
        self.site = Site.objects.create(
            name="Test Site",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)

    def _assignment(self, shift_date, *, with_start=False, with_end=False):
        row = ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=shift_date,
            start_time=time(6, 30),
            end_time=time(18, 30),
        )
        if with_start:
            Checkin.objects.create(
                assignment=row,
                guard=self.guard,
                type=Checkin.Type.START,
                latitude=1,
                longitude=1,
            )
        if with_end:
            Checkin.objects.create(
                assignment=row,
                guard=self.guard,
                type=Checkin.Type.END,
                latitude=1,
                longitude=1,
            )
        return row

    def test_collect_open_shift_without_end(self):
        self._assignment(self.yesterday, with_start=True)
        rows = collect_open_shift_rows(today=self.today)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].is_stale)
        self.assertEqual(rows[0].days_behind, 1)

    def test_excludes_completed_shift(self):
        self._assignment(self.yesterday, with_start=True, with_end=True)
        self.assertEqual(len(collect_open_shift_rows(today=self.today)), 0)

    def test_stale_count(self):
        self._assignment(self.yesterday, with_start=True)
        self._assignment(self.today, with_start=True)
        self.assertEqual(count_stale_open_shifts(today=self.today), 1)

    def test_open_shifts_page_requires_login(self):
        url = reverse("webadmin-open-shifts")
        resp = Client().get(url)
        self.assertEqual(resp.status_code, 302)

    def test_open_shifts_page_lists_row(self):
        self._assignment(self.yesterday, with_start=True)
        client = Client()
        client.login(username="admin_o", password="secret123")
        resp = client.get(reverse("webadmin-open-shifts"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "VIR-T")
        self.assertContains(resp, "Test Site")
        self.assertContains(resp, "Hier")
        self.assertContains(resp, "Valider fin")

    def test_supervisor_force_end_closes_open_shift(self):
        row = self._assignment(self.yesterday, with_start=True)
        supervisor_force_end_assignment(
            row,
            actor=self.admin,
            reason="Relève nuit absente",
        )
        row.refresh_from_db()
        self.assertEqual(row.status, ShiftAssignment.Status.COMPLETED)
        self.assertTrue(
            Checkin.objects.filter(assignment=row, type=Checkin.Type.END).exists()
        )
        self.assertEqual(len(collect_open_shift_rows(today=self.today)), 0)

    def test_supervisor_force_end_via_post(self):
        row = self._assignment(self.yesterday, with_start=True)
        client = Client()
        client.login(username="admin_o", password="secret123")
        url = reverse("webadmin-supervisor-force-end", kwargs={"pk": row.pk})
        resp = client.post(url, {"reason": "Relève absente", "next": reverse("webadmin-open-shifts")})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Checkin.objects.filter(assignment=row, type=Checkin.Type.END).exists()
        )

    def test_supervisor_force_end_rejects_without_start(self):
        row = self._assignment(self.yesterday)
        with self.assertRaises(ForceEndError):
            supervisor_force_end_assignment(row, actor=self.admin)
