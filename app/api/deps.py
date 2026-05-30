import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

from app.core.client_ip import get_client_ip
from app.core.database import Database, get_db
from app.core.firebase import verify_id_token
from app.core.roles import is_admin
from app.models.user import User

security = HTTPBearer(auto_error=True)

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", None) or get_client_ip(request)


def get_firebase_claims(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, object]:
    """Verify Firebase ID token (`Authorization: Bearer <token>`)."""
    ip = _client_ip(request)
    token = credentials.credentials

    try:
        return verify_id_token(token)
    except firebase_auth.ExpiredIdTokenError as exc:
        logger.warning("auth_failed ip=%s reason=firebase_token_expired", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except firebase_auth.RevokedIdTokenError as exc:
        logger.warning("auth_failed ip=%s reason=firebase_token_revoked", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
        ) from exc
    except firebase_auth.InvalidIdTokenError as exc:
        logger.warning("auth_failed ip=%s reason=invalid_firebase_token", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
        ) from exc
    except Exception as exc:
        logger.warning("auth_failed ip=%s reason=firebase_verify_error", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify token",
        ) from exc


def get_current_user(
    request: Request,
    db: Annotated[Database, Depends(get_db)],
    claims: Annotated[dict[str, object], Depends(get_firebase_claims)],
) -> User:
    ip = _client_ip(request)

    uid = claims.get("uid") or claims.get("sub")
    if not isinstance(uid, str) or not uid:
        logger.warning("auth_failed ip=%s reason=firebase_missing_uid", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.users.get_by_firebase_uid(uid)
    if user is not None:
        return user

    email = claims.get("email")
    if isinstance(email, str) and email.strip():
        user = db.users.get_by_email(email.lower().strip())
        if user is not None:
            user.firebase_uid = uid
            db.users.save(user)
            return user

    logger.warning("auth_failed ip=%s reason=user_not_registered uid=%s", ip, uid)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Account not found. Complete registration via POST /auth/session.",
    )


def get_current_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
