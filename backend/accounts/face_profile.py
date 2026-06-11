"""Empreinte faciale pré-calculée à l'enrôlement / mise à jour photo."""

from __future__ import annotations

from accounts.models import User
from checkins.face_verify import encode_profile_photo_field, embedding_to_list


def refresh_face_embedding_for_user(user: User, *, save: bool = True) -> tuple[bool, str]:
    """
    Calcule et enregistre l'empreinte à partir de profile_photo.
    Retourne (succès, code_erreur_vide_si_ok).
    """
    if not user.profile_photo:
        user.face_embedding = None
        if save:
            user.save(update_fields=["face_embedding"])
        return False, "no_photo"

    enc, fail = encode_profile_photo_field(user.profile_photo)
    if fail or enc is None:
        user.face_embedding = None
        if save:
            user.save(update_fields=["face_embedding"])
        return False, fail or "encode_failed"

    user.face_embedding = embedding_to_list(enc)
    if save:
        user.save(update_fields=["face_embedding"])
    return True, ""


def refresh_face_embedding_if_vigile(user: User, *, photo_updated: bool = False) -> None:
    if user.role != User.Role.VIGILE:
        return
    if photo_updated or not user.face_embedding:
        refresh_face_embedding_for_user(user)
