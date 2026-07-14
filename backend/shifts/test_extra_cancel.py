from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from checkins.models import Checkin
from shifts.extra_cancel import ExtraCancelError, cancel_extra_reinforcement
from shifts.models import ShiftAssignment
from sites.models import Site

User = get_user_model()


class ExtraCancelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_extra",
            password="secret123",
            role="admin_societe",
            is_staff=True,
        )
        self.guard = User.objects.create_user(username="VIR-X", password="x", role="vigile")
        self.site = Site.objects.create(
            name="DCR",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.today = timezone.localdate()
        self.start = time(6, 30)
        self.end = time(18, 30)

    def _extra(self, shift_date):
        return ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=shift_date,
            start_time=self.start,
            end_time=self.end,
            status=ShiftAssignment.Status.EXTRA,
        )

    def test_cancel_removes_future_days_without_checkin(self):
        self._extra(self.today)
        self._extra(self.today + timedelta(days=1))
        self._extra(self.today + timedelta(days=2))
        result = cancel_extra_reinforcement(
            site_id=self.site.pk,
            guard_id=self.guard.pk,
            start_time=self.start,
        )
        self.assertEqual(result["deleted"], 3)
        self.assertEqual(
            ShiftAssignment.objects.filter(
                guard=self.guard,
                status=ShiftAssignment.Status.EXTRA,
            ).count(),
            0,
        )

    def test_cancel_skips_days_with_start_checkin(self):
        started = self._extra(self.today)
        Checkin.objects.create(
            guard=self.guard,
            assignment=started,
            type=Checkin.Type.START,
            latitude=1,
            longitude=1,
        )
        self._extra(self.today + timedelta(days=1))
        result = cancel_extra_reinforcement(
            site_id=self.site.pk,
            guard_id=self.guard.pk,
            start_time=self.start,
        )
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["skipped_in_service"], 1)
        started.refresh_from_db()
        self.assertEqual(started.status, ShiftAssignment.Status.EXTRA)

    def test_cancel_raises_when_all_days_started(self):
        row = self._extra(self.today)
        Checkin.objects.create(
            guard=self.guard,
            assignment=row,
            type=Checkin.Type.START,
            latitude=1,
            longitude=1,
        )
        with self.assertRaises(ExtraCancelError):
            cancel_extra_reinforcement(
                site_id=self.site.pk,
                guard_id=self.guard.pk,
                start_time=self.start,
            )


class CancelExtraWebViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_extra_w",
            password="secret123",
            role="admin_societe",
            is_staff=True,
        )
        self.guard = User.objects.create_user(username="VIR-W", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Site W",
            address="Abidjan",
            expected_start_time=time(6, 30),
            expected_end_time=time(18, 30),
            latitude=1,
            longitude=1,
        )
        self.client = Client()
        self.client.login(username="admin_extra_w", password="secret123")
        self.today = timezone.localdate()
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.today + timedelta(days=3),
            start_time=time(6, 30),
            end_time=time(18, 30),
            status=ShiftAssignment.Status.EXTRA,
        )

    def test_cancel_extra_via_post(self):
        url = reverse("webadmin-cancel-extra")
        resp = self.client.post(
            url,
            {
                "site_id": self.site.pk,
                "guard_id": self.guard.pk,
                "start_time": "06:30:00",
                "next": reverse("webadmin-affectations"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            ShiftAssignment.objects.filter(status=ShiftAssignment.Status.EXTRA).count(),
            0,
        )
