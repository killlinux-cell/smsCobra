import base64
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from shifts.models import ShiftAssignment
from sites.models import Site

from .models import ControllerSiteAssignment, ControllerVisit

User = get_user_model()

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class FCMTokenAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin-fcm",
            password="testpass123",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.vigile = User.objects.create_user(
            username="vigile-fcm",
            password="testpass123",
            role=User.Role.VIGILE,
        )

    def _auth_header(self, user):
        refresh = RefreshToken.for_user(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

    def test_admin_can_register_fcm_token(self):
        url = "/api/v1/me/fcm-token"
        resp = self.client.post(
            url,
            {"fcm_token": "fake-fcm-token-abc123"},
            format="json",
            **self._auth_header(self.admin),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.fcm_token, "fake-fcm-token-abc123")

    def test_vigile_forbidden(self):
        url = "/api/v1/me/fcm-token"
        resp = self.client.post(
            url,
            {"fcm_token": "should-not-save"},
            format="json",
            **self._auth_header(self.vigile),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_fcm_token(self):
        self.admin.fcm_token = "old"
        self.admin.save(update_fields=["fcm_token"])
        url = "/api/v1/me/fcm-token"
        resp = self.client.delete(url, **self._auth_header(self.admin))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.fcm_token, "")


class VigileFaceLoginAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        self.vigile = User.objects.create_user(
            username="VIR-001",
            password="unused-for-face-login",
            role=User.Role.VIGILE,
        )
        self.vigile.profile_photo = photo
        self.vigile.save()

    @patch("accounts.views.verify_selfie_against_profile", return_value=(True, 0.9, ""))
    def test_face_login_returns_jwt(self, _mock):
        selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/face-login",
            {"username": "vir-001", "selfie": selfie},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_face_login_rejects_admin(self):
        admin = User.objects.create_user(
            username="admin-x",
            password="p",
            role=User.Role.ADMIN_SOCIETE,
        )
        selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/face-login",
            {"username": "admin-x", "selfie": selfie},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class VigileFaceIdentifyAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = Site.objects.create(
            name="Site X",
            address="Abidjan",
            expected_start_time=time(8, 0),
            expected_end_time=time(17, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        self.vigile = User.objects.create_user(
            username="VIR-222",
            password="x",
            role=User.Role.VIGILE,
            profile_photo=photo,
        )
        ShiftAssignment.objects.create(
            guard=self.vigile,
            site=self.site,
            shift_date=date.today(),
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

    @patch("accounts.views.verify_selfie_against_profile", return_value=(True, 0.93, ""))
    def test_face_identify_returns_tokens_for_planned_guard(self, _mock):
        selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/face-identify",
            {"selfie": selfie, "site_id": self.site.id},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertEqual(resp.data.get("guard_username"), "VIR-222")

    @patch("accounts.views.verify_selfie_against_profile", return_value=(True, 0.93, ""))
    def test_face_identify_without_site_id_still_identifies_planned_guard(self, _mock):
        selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/face-identify",
            {"selfie": selfie},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get("guard_username"), "VIR-222")

    @patch("accounts.views.verify_selfie_against_profile", return_value=(False, 0.1, "face_mismatch"))
    def test_face_identify_refuses_unknown_face(self, _mock):
        selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/face-identify",
            {"selfie": selfie, "site_id": self.site.id},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ControllerFaceCheckinAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.site = Site.objects.create(
            name="Site Controle",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.348,
            longitude=-4.024,
        )
        photo = SimpleUploadedFile("ctrl.png", _PNG_1PX, content_type="image/png")
        self.controller = User.objects.create_user(
            username="CTR-001",
            password="unused",
            role=User.Role.CONTROLEUR,
            profile_photo=photo,
        )
        ControllerSiteAssignment.objects.create(controller=self.controller, site=self.site)

    @patch("accounts.views.verify_selfie_against_profile", return_value=(True, 0.88, ""))
    def test_controller_face_checkin_records_visit(self, _mock):
        selfie = SimpleUploadedFile("selfie.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/controller-face-checkin",
            {"selfie": selfie, "site_id": self.site.id, "device_id": "pix-01"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data.get("ok"))
        self.assertEqual(resp.data.get("controller_id"), self.controller.id)
        self.assertEqual(ControllerVisit.objects.count(), 1)

    @patch("accounts.views.verify_selfie_against_profile", return_value=(False, 0.2, "face_mismatch"))
    def test_controller_face_checkin_refuses_unknown_face(self, _mock):
        selfie = SimpleUploadedFile("selfie.png", _PNG_1PX, content_type="image/png")
        resp = self.client.post(
            "/api/v1/auth/controller-face-checkin",
            {"selfie": selfie, "site_id": self.site.id},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ControllerVisit.objects.count(), 0)

    def test_entry_sites_lists_active_sites(self):
        Site.objects.create(
            name="Site Inactif",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            latitude=5.34,
            longitude=-4.02,
            is_active=False,
        )
        resp = self.client.get("/api/v1/entry/sites")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(any(row.get("name") == "Site Controle" for row in resp.data))
        self.assertFalse(any(row.get("name") == "Site Inactif" for row in resp.data))
