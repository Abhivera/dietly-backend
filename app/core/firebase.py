"""Firebase Admin SDK — verify ID tokens from the web/mobile clients."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from app.core.config import settings

logger = logging.getLogger(__name__)

_app_initialized = False


def _load_credentials() -> credentials.Base:
    path = settings.firebase_credentials_path
    if path:
        cred_path = Path(path).expanduser()
        if not cred_path.is_file():
            raise FileNotFoundError(f"Firebase credentials file not found: {cred_path}")
        return credentials.Certificate(str(cred_path))

    raw = settings.firebase_credentials_json
    if raw:
        return credentials.Certificate(json.loads(raw))

    raise RuntimeError(
        "Firebase Admin is not configured. Set FIREBASE_CREDENTIALS_PATH "
        "or FIREBASE_CREDENTIALS_JSON in the environment."
    )


def init_firebase() -> None:
    global _app_initialized
    if _app_initialized:
        return
    cred = _load_credentials()
    firebase_admin.initialize_app(
        cred,
        options={"projectId": settings.firebase_project_id} if settings.firebase_project_id else None,
    )
    _app_initialized = True
    logger.info("firebase_admin_initialized project_id=%s", settings.firebase_project_id or "default")


def verify_id_token(token: str) -> dict[str, object]:
    init_firebase()
    return firebase_auth.verify_id_token(token, check_revoked=True)
