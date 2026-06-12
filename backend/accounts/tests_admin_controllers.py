import base64
from unittest.mock import patch

from datetime import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import ControllerSiteAssignment, User
from sites.models import Site

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class AdminControllerAPITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ADM-CTRL",
            password="secret123",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.site_a = Site.objects.create(
            name="Site Alpha",
            address="Abidjan",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            is_active=True,
        )
        self.site_b = Site.objects.create(
            name="Site Beta",
            address="Yamoussoukro",
            expected_start_time=time(6, 0),
            expected_end_time=time(18, 0),
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.photo = SimpleUploadedFile("portrait.jpg", _PNG_1PX, content_type="image/jpeg")

    @patch(
        "accounts.serializers_admin.validate_profile_photo_upload",
        return_value=(True, ""),
    )
    def test_create_controller_auto_username_and_sites(self, _mock):
        resp = self.client.post(
            "/api/v1/admin/controllers/",
            {
                "first_name": "Paul",
                "last_name": "Kouame",
                "phone_number": "0700000001",
                "site_ids": f"{self.site_a.id},{self.site_b.id}",
                "profile_photo": self.photo,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data["username"].startswith("CTR-"))
        self.assertTrue(resp.data["portrait_ok"])
        self.assertEqual(len(resp.data["authorized_site_ids"]), 2)
        controller = User.objects.get(pk=resp.data["id"])
        self.assertEqual(controller.role, User.Role.CONTROLEUR)
        self.assertEqual(
            ControllerSiteAssignment.objects.filter(controller=controller).count(),
            2,
        )

    @patch(
        "accounts.serializers_admin.validate_profile_photo_upload",
        return_value=(False, "no_face_in_reference"),
    )
    def test_create_controller_rejects_invalid_portrait(self, _mock):
        resp = self.client.post(
            "/api/v1/admin/controllers/",
            {
                "first_name": "Bad",
                "profile_photo": self.photo,
            },
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("profile_photo", resp.data)

    def test_list_controllers(self):
        User.objects.create_user(
            username="CTR-001",
            password="x",
            role=User.Role.CONTROLEUR,
            first_name="Existant",
        )
        resp = self.client.get("/api/v1/admin/controllers/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["username"], "CTR-001")
