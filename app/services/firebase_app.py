"""Initialize Firebase Admin SDK once per process."""

from __future__ import annotations

import logging
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)
_initialized = False


def init_firebase() -> None:
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return

    cred_path = settings.firebase_credentials_path
    if not cred_path or not Path(cred_path).is_file():
        raise RuntimeError(
            "Set FIREBASE_CREDENTIALS_PATH in .env to the absolute path of your Firebase service account JSON file."
        )

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin initialized")

    _initialized = True
