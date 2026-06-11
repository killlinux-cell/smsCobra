from datetime import time

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from shifts.dispatch_candidates import (
    is_guard_eligible_for_dispatch,
    replacement_candidate_queryset,
)
from shifts.models import ShiftAssignment
from sites.models import Site


class DispatchCandidatesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ADM-DISP",
            password="x",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.site_a = Site.objects.create(
            name="Site A",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.35,
            longitude=-4.03,
            site_manager_phone="+2250700000001",
        )
        self.site_b = Site.objects.create(
            name="Site B",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.36,
            longitude=-4.04,
            site_manager_phone="+2250700000002",
        )
        self.titular = self._vigile("VIR-TIT", face=True)
        self.free = self._vigile("VIR-FREE", face=True)
        self.busy = self._vigile("VIR-BUSY", face=True)
        self.no_face = self._vigile("VIR-NOFACE", face=False)
        self.today = timezone.localdate()
        self.assignment = ShiftAssignment.objects.create(
            guard=self.titular,
            site=self.site_a,
            shift_date=self.today,
            start_time=time(6, 0),
            end_time=time(18, 0),
        )
        ShiftAssignment.objects.create(
            guard=self.busy,
            site=self.site_b,
            shift_date=self.today,
            start_time=time(6, 0),
            end_time=time(18, 0),
        )

    @staticmethod
    def _vigile(username: str, *, face: bool) -> User:
        from django.core.files.uploadedfile import SimpleUploadedFile

        u = User.objects.create_user(
            username=username,
            password="x",
            role=User.Role.VIGILE,
        )
        if face:
            u.profile_photo.save(
                "p.jpg",
                SimpleUploadedFile("p.jpg", b"jpeg", content_type="image/jpeg"),
            )
            u.face_embedding = [0.0] * 128
            u.save(update_fields=["face_embedding"])
        return u

    def test_replacement_candidates_excludes_busy_and_titular(self):
        ids = set(replacement_candidate_queryset(self.assignment).values_list("pk", flat=True))
        self.assertIn(self.free.pk, ids)
        self.assertNotIn(self.titular.pk, ids)
        self.assertNotIn(self.busy.pk, ids)
        self.assertNotIn(self.no_face.pk, ids)

    def test_api_dispatch_candidates(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.get(
            f"/api/v1/admin/alerts/dispatch-candidates?assignment_id={self.assignment.pk}"
        )
        self.assertEqual(resp.status_code, 200)
        usernames = {row["username"] for row in resp.data}
        self.assertIn("VIR-FREE", usernames)
        self.assertNotIn("VIR-TIT", usernames)
        self.assertNotIn("VIR-BUSY", usernames)

    def test_is_guard_eligible_helper(self):
        ok, _ = is_guard_eligible_for_dispatch(self.assignment, self.free)
        self.assertTrue(ok)
        ok, reason = is_guard_eligible_for_dispatch(self.assignment, self.busy)
        self.assertFalse(ok)
        self.assertTrue(reason)
