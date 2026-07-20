from datetime import date, timedelta, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from shifts.models import FixedPost, ShiftAssignment
from sites.models import Site

User = get_user_model()


class SystemRefreshViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_refresh",
            password="secret",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.guard = User.objects.create_user(username="orphan_g", password="x", role="vigile")
        self.site = Site.objects.create(
            name="Refresh Site",
            address="Abidjan",
            day_staff_required=1,
            night_staff_required=1,
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=1,
            longitude=1,
        )
        self.day = timezone.localdate() + timedelta(days=3)
        ShiftAssignment.objects.create(
            guard=self.guard,
            site=self.site,
            shift_date=self.day,
            start_time=time(18, 0),
            end_time=time(6, 0),
            status=ShiftAssignment.Status.SCHEDULED,
        )

    def test_refresh_purges_orphans_and_redirects_back(self):
        self.client.force_login(self.admin)
        url = reverse("webadmin-system-refresh")
        next_path = reverse("webadmin-affectations")
        with patch("alerts.tasks.detect_missed_shift_task") as mock_task:
            mock_task.delay.return_value = None
            response = self.client.post(url, {"next": next_path})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_path)
        self.assertFalse(
            ShiftAssignment.objects.filter(
                site=self.site,
                guard=self.guard,
                status=ShiftAssignment.Status.SCHEDULED,
            ).exists()
        )

    def test_refresh_with_fixed_post_does_not_500(self):
        FixedPost.objects.create(
            site=self.site,
            shift_type=FixedPost.ShiftType.NIGHT,
            titular_guard=self.guard,
            is_active=True,
        )
        self.client.force_login(self.admin)
        url = reverse("webadmin-system-refresh")
        with patch("alerts.tasks.detect_missed_shift_task") as mock_task:
            mock_task.delay.return_value = None
            response = self.client.post(url, {"next": reverse("webadmin-dashboard")})
        self.assertEqual(response.status_code, 302)

    def test_refresh_requires_post(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("webadmin-system-refresh"))
        self.assertEqual(response.status_code, 405)
