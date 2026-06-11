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
# Redimensionne avant détection (photos téléphone souvent 5–8 Mo en prod).
DEFAULT_MAX_IMAGE_SIDE = 960


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


def _face_locations(image, model: str):
    import face_recognition

    return face_recognition.face_locations(image, model=model)


def _largest_face_location(image, model: str):
    locs = _face_locations(image, model=model)
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


def _max_image_side() -> int:
    return int(getattr(settings, "FACE_IMAGE_MAX_SIDE", DEFAULT_MAX_IMAGE_SIDE))


def _resize_rgb_array(image: np.ndarray, max_side: int) -> np.ndarray:
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    pil = Image.fromarray(image)
    pil = pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(pil)


def _load_rgb_image_with_exif(path: str):
    """
    Charge une image en RGB en appliquant l'orientation EXIF.

    Certains appareils (ex. certains Pixel) stockent l'orientation dans EXIF ;
    sans normalisation, le détecteur facial peut échouer alors que le visage est présent.
    """
    with Image.open(path) as img:
        fixed = ImageOps.exif_transpose(img).convert("RGB")
        arr = np.array(fixed)
    return _resize_rgb_array(arr, _max_image_side())


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


def encode_selfie_upload(selfie) -> Tuple[np.ndarray | None, str]:
    """
    Encode le selfie une seule fois (à réutiliser pour plusieurs comparaisons).
    Retourne (encodage_128d, code_raison_vide_si_ok).
    """
    try:
        import face_recognition  # noqa: F401
    except ImportError:
        logger.error("face_recognition non installé : pip install face-recognition")
        return None, "face_engine_unavailable"

    model = getattr(settings, "FACE_VERIFICATION_MODEL", "hog")
    num_jitters = int(getattr(settings, "FACE_VERIFICATION_NUM_JITTERS", 1))
    selfie_path = _temp_path("cobra_selfie", ".jpg")
    try:
        _write_source_to_path(selfie, selfie_path)
        selfie_img = _load_rgb_image_with_exif(selfie_path)
        enc = _selfie_encoding_with_rotation_fallback(
            selfie_img, model=model, num_jitters=num_jitters
        )
        if enc is None:
            return None, "no_face_in_selfie"
        return enc, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur encodage selfie: %s", exc)
        return None, "face_verify_error"
    finally:
        try:
            if os.path.isfile(selfie_path):
                os.unlink(selfie_path)
        except OSError:
            pass


def embedding_to_list(encoding: np.ndarray) -> list[float]:
    return [float(x) for x in encoding.tolist()]


def encoding_from_list(stored) -> np.ndarray | None:
    if not stored or not isinstance(stored, list) or len(stored) < 128:
        return None
    try:
        return np.array(stored, dtype=np.float64)
    except (TypeError, ValueError):
        return None


ENROLLMENT_PHOTO_MESSAGES = {
    "no_face_in_reference": (
        "Aucun visage détecté. Reprenez le portrait : visage centré, de face, "
        "bien éclairé, sans lunettes de soleil ni masque."
    ),
    "multiple_faces_in_reference": (
        "Plusieurs visages détectés. Une seule personne doit être visible sur la photo."
    ),
    "face_engine_unavailable": (
        "Moteur de reconnaissance faciale indisponible. "
        "Réessayez plus tard ou contactez l'administrateur."
    ),
    "face_verify_error": (
        "Impossible d'analyser la photo. Réessayez avec une autre image."
    ),
}


def _image_with_rotation_face_fallback(image, model: str):
    """Retourne (image_orientée, nombre_de_visages) avec rotations si besoin."""
    count = len(_face_locations(image, model=model))
    if count > 0:
        return image, count
    for k in (1, 2, 3):
        rotated = np.rot90(image, k)
        count = len(_face_locations(rotated, model=model))
        if count > 0:
            return rotated, count
    return image, 0


def _load_rgb_image_from_source(source):
    """Charge une image uploadée ou un champ fichier en RGB (EXIF + redimensionnement)."""
    from django.db.models.fields.files import FieldFile

    ref_path = _temp_path("cobra_ref", ".jpg")
    try:
        # UploadedFile : ne pas utiliser ``with source.open()`` — le context manager
        # fermerait le fichier avant que Django ne l'enregistre (erreur 500 webadmin).
        if isinstance(source, UploadedFile):
            _write_source_to_path(source, ref_path)
        elif isinstance(source, FieldFile):
            with source.open("rb") as ref_stream:
                _write_source_to_path(ref_stream, ref_path)
        elif hasattr(source, "open"):
            with source.open("rb") as ref_stream:
                _write_source_to_path(ref_stream, ref_path)
        else:
            _write_source_to_path(source, ref_path)
        return _load_rgb_image_with_exif(ref_path), ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur chargement photo profil: %s", exc)
        return None, "face_verify_error"
    finally:
        try:
            if os.path.isfile(ref_path):
                os.unlink(ref_path)
        except OSError:
            pass


def validate_profile_photo_upload(source) -> Tuple[bool, str]:
    """
    Valide une photo portrait à l'enrôlement (création / mise à jour vigile).
    Retourne (succès, code_raison_vide_si_ok).
    """
    try:
        import face_recognition  # noqa: F401
    except ImportError:
        logger.error("face_recognition non installé : pip install face-recognition")
        return False, "face_engine_unavailable"

    if not source:
        return False, "no_face_in_reference"

    model = getattr(settings, "FACE_VERIFICATION_MODEL", "hog")
    num_jitters = int(getattr(settings, "FACE_VERIFICATION_NUM_JITTERS", 1))

    try:
        ref_img, load_fail = _load_rgb_image_from_source(source)
        if load_fail or ref_img is None:
            return False, load_fail or "face_verify_error"

        ref_img, face_count = _image_with_rotation_face_fallback(ref_img, model=model)
        if face_count == 0:
            return False, "no_face_in_reference"
        if face_count > 1:
            return False, "multiple_faces_in_reference"

        ref_enc = _encoding_for_largest_face(ref_img, model=model, num_jitters=num_jitters)
        if ref_enc is None:
            return False, "no_face_in_reference"
        return True, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur validation photo portrait: %s", exc)
        return False, "face_verify_error"


def encode_profile_photo_field(profile_image_field) -> Tuple[np.ndarray | None, str]:
    """Encode la photo portrait (enrôlement) une fois."""
    ok, fail = validate_profile_photo_upload(profile_image_field)
    if not ok:
        return None, fail

    model = getattr(settings, "FACE_VERIFICATION_MODEL", "hog")
    num_jitters = int(getattr(settings, "FACE_VERIFICATION_NUM_JITTERS", 1))
    ref_path = _temp_path("cobra_ref", ".jpg")
    try:
        with profile_image_field.open("rb") as ref_stream:
            _write_source_to_path(ref_stream, ref_path)
        ref_img = _load_rgb_image_with_exif(ref_path)
        ref_img, _face_count = _image_with_rotation_face_fallback(ref_img, model=model)
        ref_enc = _encoding_for_largest_face(ref_img, model=model, num_jitters=num_jitters)
        if ref_enc is None:
            return None, "no_face_in_reference"
        return ref_enc, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur encodage photo profil: %s", exc)
        return None, "face_verify_error"
    finally:
        try:
            if os.path.isfile(ref_path):
                os.unlink(ref_path)
        except OSError:
            pass


def _reference_encoding(
    profile_image_field,
    *,
    profile_user=None,
) -> Tuple[np.ndarray | None, str]:
    if profile_user is not None:
        stored = encoding_from_list(getattr(profile_user, "face_embedding", None))
        if stored is not None:
            return stored, ""
    return encode_profile_photo_field(profile_image_field)


def verify_selfie_against_profile(
    selfie: UploadedFile,
    profile_image_field,
    *,
    selfie_encoding: np.ndarray | None = None,
    profile_user=None,
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

    try:
        if selfie_encoding is None:
            selfie_enc, fail = encode_selfie_upload(selfie)
            if fail:
                return False, None, fail
        else:
            selfie_enc = selfie_encoding

        ref_enc, ref_fail = _reference_encoding(
            profile_image_field,
            profile_user=profile_user,
        )
        if ref_fail or ref_enc is None:
            return False, None, ref_fail or "no_face_in_reference"

        import face_recognition

        dist = float(face_recognition.face_distance([ref_enc], selfie_enc)[0])
        score = max(0.0, min(1.0, 1.0 - dist))

        if dist <= tolerance:
            return True, score, ""

        return False, score, "face_mismatch"
    except Exception as exc:  # noqa: BLE001 — log + refus sécurisé
        logger.exception("Erreur lors de la vérification faciale: %s", exc)
        return False, None, "face_verify_error"
