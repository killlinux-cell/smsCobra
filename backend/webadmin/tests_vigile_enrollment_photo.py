import base64
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from webadmin.forms import VigileCreationForm, VigileUpdateForm

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
