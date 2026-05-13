"""
Initialisation Firebase Admin SDK pour l'envoi des notifications FCM.

Chemins supportés (priorité) :
1) FCM_CREDENTIALS_PATH ou GOOGLE_APPLICATION_CREDENTIALS : chemin vers le JSON
   « Compte de service » Firebase.
2) Fichier local : backend/secrets/firebase-service-account.json (dossier gitignoré).
3) FCM_SERVICE_ACCOUNT_JSON : contenu JSON complet (hébergeurs sans fichier disque).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_credentials_path() -> str:
    """Chemin absolu vers le JSON compte de service (env, puis fichier local conventionnel)."""
    for key in ("FCM_CREDENTIALS_PATH", "GOOGLE_APPLICATION_CREDENTIALS"):
        p = (os.getenv(key) or "").strip()
        if p and os.path.isfile(p):
            return p
    try:
        from django.conf import settings

        default = Path(settings.BASE_DIR) / "secrets" / "firebase-service-account.json"
        if default.is_file():
            return str(default)
    except Exception:
        pass
    return ""


def init_firebase() -> bool:
    """Initialise l'app Firebase si des identifiants sont fournis. Retourne True si prêt."""
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning("firebase_admin absent : notifications push désactivées.")
        return False

    if firebase_admin._apps:
        return True

    cred_path = _resolve_credentials_path()
    cred_json_raw = os.getenv("FCM_SERVICE_ACCOUNT_JSON", "").strip()

    try:
        if cred_json_raw:
            info = json.loads(cred_json_raw)
            cred = credentials.Certificate(info)
        elif cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            logger.warning(
                "FCM non configuré : placez le JSON dans backend/secrets/firebase-service-account.json "
                "(non versionné), ou définissez FCM_CREDENTIALS_PATH, GOOGLE_APPLICATION_CREDENTIALS "
                "ou FCM_SERVICE_ACCOUNT_JSON. Les alertes s’affichent sur le tableau de bord, "
                "mais pas de push téléphone."
            )
            return False

        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin initialisé : envoi des notifications push possible.")
        return True
    except Exception:
        logger.exception("Échec de l’initialisation Firebase (vérifiez le JSON / le chemin).")
        return False


def is_firebase_initialized() -> bool:
    try:
        import firebase_admin

        return bool(firebase_admin._apps)
    except ImportError:
        return False
