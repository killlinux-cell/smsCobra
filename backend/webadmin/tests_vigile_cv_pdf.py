import base64
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import User
from webadmin.vigile_cv_pdf import build_vigile_cv_pdf

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class VigileCvPdfTests(TestCase):
    def setUp(self):
        photo = SimpleUploadedFile("portrait.jpg", _PNG_1PX, content_type="image/jpeg")
        recto = SimpleUploadedFile("id-recto.jpg", _PNG_1PX, content_type="image/jpeg")
        verso = SimpleUploadedFile("id-verso.jpg", _PNG_1PX, content_type="image/jpeg")
        self.vigile = User.objects.create_user(
            username="VIR-CV",
            password="x",
            role=User.Role.VIGILE,
            first_name="Test",
            last_name="Vigile",
            profile_photo=photo,
            id_document=recto,
            id_document_verso=verso,
            date_integration=date(2024, 1, 15),
        )

    def test_build_cv_pdf_includes_images(self):
        data = build_vigile_cv_pdf(self.vigile)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 3000)

    def test_build_cv_pdf_without_documents_still_works(self):
        bare = User.objects.create_user(
            username="VIR-BARE",
            password="x",
            role=User.Role.VIGILE,
        )
        data = build_vigile_cv_pdf(bare)
        self.assertTrue(data.startswith(b"%PDF"))
