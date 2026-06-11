import base64
import sys
from unittest.mock import MagicMock, patch

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.face_profile import refresh_face_embedding_for_user
from accounts.models import User
from checkins.face_verify import embedding_to_list, encoding_from_list, verify_selfie_against_profile

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_FAKE_ENC = np.zeros(128, dtype=np.float64)


class FaceEmbeddingTests(TestCase):
    def setUp(self):
        photo = SimpleUploadedFile("p.png", _PNG_1PX, content_type="image/png")
        self.vigile = User.objects.create_user(
            username="VIR-EMB",
            password="x",
            role=User.Role.VIGILE,
            profile_photo=photo,
        )

    @patch(
        "accounts.face_profile.encode_profile_photo_field",
        return_value=(_FAKE_ENC, ""),
    )
    def test_refresh_stores_embedding(self, _mock):
        ok, fail = refresh_face_embedding_for_user(self.vigile)
        self.assertTrue(ok)
        self.assertEqual(fail, "")
        self.vigile.refresh_from_db()
        self.assertEqual(len(self.vigile.face_embedding), 128)

    @patch("checkins.face_verify.encode_selfie_upload", return_value=(_FAKE_ENC, ""))
    def test_verify_uses_stored_embedding(self, _mock_selfie):
        self.vigile.face_embedding = embedding_to_list(_FAKE_ENC)
        self.vigile.save(update_fields=["face_embedding"])

        mock_fr = MagicMock()
        mock_fr.face_distance.return_value = [0.2]
        with patch.dict(sys.modules, {"face_recognition": mock_fr}):
            selfie = SimpleUploadedFile("s.png", _PNG_1PX, content_type="image/png")
            ok, score, fail = verify_selfie_against_profile(
                selfie,
                self.vigile.profile_photo,
                profile_user=self.vigile,
            )
        self.assertTrue(ok)
        self.assertIsNotNone(score)
        self.assertEqual(fail, "")
        mock_fr.face_distance.assert_called_once()

    def test_encoding_from_list_invalid(self):
        self.assertIsNone(encoding_from_list([]))
        self.assertIsNone(encoding_from_list(None))
