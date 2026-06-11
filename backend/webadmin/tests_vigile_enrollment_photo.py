import base64
from unittest.mock import patch

import numpy as np
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from webadmin.forms import VigileCreationForm, VigileUpdateForm

User = get_user_model()

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class VigileEnrollmentPhotoFormTests(TestCase):
    @patch(
        "webadmin.forms.validate_profile_photo_upload",
        return_value=(False, "no_face_in_reference"),
    )
    def test_creation_form_rejects_invalid_portrait(self, _mock):
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        form = VigileCreationForm(
            data={"username": "VIR-999"},
            files={"profile_photo": photo},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("profile_photo", form.errors)

    @patch(
        "webadmin.forms.validate_profile_photo_upload",
        return_value=(True, ""),
    )
    def test_creation_form_accepts_valid_portrait(self, _mock):
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        form = VigileCreationForm(
            data={"username": "VIR-998", "first_name": "Jean"},
            files={"profile_photo": photo},
        )
        self.assertTrue(form.is_valid(), form.errors)

    @patch(
        "webadmin.forms.validate_profile_photo_upload",
        return_value=(False, "multiple_faces_in_reference"),
    )
    def test_update_form_rejects_new_invalid_portrait(self, _mock):
        from accounts.models import User

        vigile = User.objects.create_user(
            username="VIR-UPD",
            password="x",
            role=User.Role.VIGILE,
        )
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        form = VigileUpdateForm(
            data={"username": "VIR-UPD", "is_active": "on"},
            files={"profile_photo": photo},
            instance=vigile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("profile_photo", form.errors)


class VigileCreationWebViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ADM-WEB-V",
            password="secret123",
            role=User.Role.ADMIN_SOCIETE,
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.photo = SimpleUploadedFile(
            "portrait.jpg",
            _PNG_1PX,
            content_type="image/jpeg",
        )

    @patch(
        "webadmin.forms.validate_profile_photo_upload",
        return_value=(True, ""),
    )
    @patch(
        "accounts.face_profile.encode_profile_photo_field",
        return_value=(np.zeros(128), ""),
    )
    def test_vigiles_post_creates_guard(self, _enc, _val):
        url = reverse("webadmin-vigiles")
        resp = self.client.post(
            url,
            {
                "username": "",
                "first_name": "Kouadio",
                "last_name": "Jean",
                "email": "kouadio@example.com",
                "phone_number": "+2250700000001",
                "profile_photo": self.photo,
            },
        )
        self.assertEqual(resp.status_code, 302, resp.content[:500])
        self.assertTrue(
            User.objects.filter(role=User.Role.VIGILE, first_name="Kouadio").exists()
        )


class UploadedPhotoStaysOpenTests(TestCase):
    """Régression : la validation ne doit pas fermer le fichier avant save()."""

    @patch(
        "checkins.face_verify._load_rgb_image_with_exif",
        return_value=np.zeros((64, 64, 3), dtype=np.uint8),
    )
    def test_load_rgb_keeps_upload_open(self, _exif):
        from checkins.face_verify import _load_rgb_image_from_source
        from webadmin.forms import _clean_enrollment_profile_photo

        photo = SimpleUploadedFile("portrait.jpg", _PNG_1PX, content_type="image/jpeg")
        _img, fail = _load_rgb_image_from_source(photo)
        self.assertEqual(fail, "")
        photo.seek(0)

        with patch(
            "webadmin.forms.validate_profile_photo_upload",
            return_value=(True, ""),
        ):
            photo2 = SimpleUploadedFile("portrait2.jpg", _PNG_1PX, content_type="image/jpeg")
            cleaned = _clean_enrollment_profile_photo(photo2)
            self.assertIs(cleaned, photo2)
            cleaned.seek(0)
