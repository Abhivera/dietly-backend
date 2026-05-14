import logging

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.database import get_db
from app.core.roles import UserRole, is_admin
from app.models.user import User

security = HTTPBearer(auto_error=True)

logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", None) or get_client_ip(request)


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """Verify Firebase ID token and return the app user (auto-provision on first login)."""
    ip = _client_ip(request)
    id_token = credentials.credentials
    try:
        claims = firebase_auth.verify_id_token(id_token, check_revoked=False)
    except Exception as exc:
        logger.warning(
            "auth_verify_failed ip=%s reason=invalid_or_expired_token error=%s",
            ip,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
        ) from exc

    uid = claims.get("uid")
    if not uid:
        logger.warning("auth_failed ip=%s reason=token_missing_uid", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing uid",
        )

    user = db.query(User).filter(User.firebase_uid == uid).first()
    if user:
        return user

    email = claims.get("email")
    if not email:
        logger.warning("auth_failed ip=%s reason=token_missing_email uid=%s", ip, uid)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token must include an email claim",
        )

    full_name = claims.get("name") or email.split("@")[0]
    picture = claims.get("picture")

    user = User(
        firebase_uid=uid,
        email=email,
        full_name=full_name,
        avatar_url=picture or settings.default_avatar_url,
        role=UserRole.user.value,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        logger.exception(
            "user_provision_failed ip=%s firebase_uid=%s email=%s",
            ip,
            uid,
            email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create user profile",
        ) from exc

    return user


def get_current_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
