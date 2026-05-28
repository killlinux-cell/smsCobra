"""
Comparaison selfie vs photo de profil (enrôlement vigile).

Utilise la bibliothèque `face_recognition` (dlib) : encodage 128D puis distance euclidienne.
Seuil configurable via FACE_VERIFICATION_TOLERANCE (plus bas = plus strict).
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import Tuple

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Plus la distance est faible, plus les visages sont similaires (typiquement < 0.6 = même personne).
DEFAULT_TOLERANCE = 0.55


def _temp_path(prefix: str, suffix: str) -> str:
    return os.path.join(
        tempfile.gettempdir(),
        f"{prefix}_{uuid.uuid4().hex}{suffix}",
    )


def _write_source_to_path(source, path: str) -> None:
    """Écrit un UploadedFile ou un flux binaire vers un chemin disque."""
    try:
        source.seek(0)
    except (AttributeError, OSError):
        pass
    with open(path, "wb") as out:
        if hasattr(source, "chunks"):
            for chunk in source.chunks():
                out.write(chunk)
        else:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                out.write(chunk)


def _largest_face_location(image, model: str):
    import face_recognition

    locs = face_recognition.face_locations(image, model=model)
    if not locs:
        return None

    def area(loc):
        top, right, bottom, left = loc
        return max(0, (bottom - top) * (right - left))

    return max(locs, key=area)


def _encoding_for_largest_face(image, model: str, num_jitters: int):
    import face_recognition

    loc = _largest_face_location(image, model=model)
    if loc is None:
        return None
    encs = face_recognition.face_encodings(image, [loc], num_jitters=num_jitters)
    return encs[0] if encs else None


def _load_rgb_image_with_exif(path: str):
    """
    Charge une image en RGB en appliquant l'orientation EXIF.

    Certains appareils (ex. certains Pixel) stockent l'orientation dans EXIF ;
    sans normalisation, le détecteur facial peut échouer alors que le visage est présent.
    """
    with Image.open(path) as img:
        fixed = ImageOps.exif_transpose(img).convert("RGB")
        return np.array(fixed)


def _selfie_encoding_with_rotation_fallback(image, model: str, num_jitters: int):
    """
    Tente l'encodage du selfie avec rotations successives.
    """
    enc = _encoding_for_largest_face(image, model=model, num_jitters=num_jitters)
    if enc is not None:
        return enc
    # Fallback robuste pour orientation capricieuse selon marque/modèle.
    for k in (1, 2, 3):  # 90, 180, 270
        rotated = np.rot90(image, k)
        enc = _encoding_for_largest_face(rotated, model=model, num_jitters=num_jitters)
        if enc is not None:
            return enc
    return None


def verify_selfie_against_profile(
    selfie: UploadedFile,
    profile_image_field,
) -> Tuple[bool, float | None, str]:
    """
    Retourne (succès, score_qualité_0_1_ou_None, code_raison).

    score : 1 - distance (borné), plus haut = meilleure correspondance.
    """
    try:
        import face_recognition  # noqa: F401
    except ImportError:
        logger.error("face_recognition non installé : pip install face-recognition")
        return False, None, "face_engine_unavailable"

    tolerance = float(
        getattr(settings, "FACE_VERIFICATION_TOLERANCE", DEFAULT_TOLERANCE)
    )
    model = getattr(settings, "FACE_VERIFICATION_MODEL", "hog")
    num_jitters = int(getattr(settings, "FACE_VERIFICATION_NUM_JITTERS", 1))

    selfie_path = _temp_path("cobra_selfie", ".jpg")
    ref_path = _temp_path("cobra_ref", ".jpg")
    try:
        _write_source_to_path(selfie, selfie_path)

        with profile_image_field.open("rb") as ref_stream:
            _write_source_to_path(ref_stream, ref_path)

        import face_recognition

        selfie_img = _load_rgb_image_with_exif(selfie_path)
        ref_img = _load_rgb_image_with_exif(ref_path)

        ref_enc = _encoding_for_largest_face(ref_img, model=model, num_jitters=num_jitters)
        if ref_enc is None:
            return False, None, "no_face_in_reference"

        selfie_enc = _selfie_encoding_with_rotation_fallback(
            selfie_img, model=model, num_jitters=num_jitters
        )
        if selfie_enc is None:
            return False, None, "no_face_in_selfie"

        dist = float(face_recognition.face_distance([ref_enc], selfie_enc)[0])
        score = max(0.0, min(1.0, 1.0 - dist))

        if dist <= tolerance:
            return True, score, ""

        return False, score, "face_mismatch"
    except Exception as exc:  # noqa: BLE001 — log + refus sécurisé
        logger.exception("Erreur lors de la vérification faciale: %s", exc)
        return False, None, "face_verify_error"
    finally:
        for p in (selfie_path, ref_path):
            try:
                if os.path.isfile(p):
                    os.unlink(p)
            except OSError:
                pass
