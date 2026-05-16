import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.client_ip import get_client_ip
from app.core.database import get_db
from app.core.roles import is_admin
from app.core.security import decode_access_token
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
    """Resolve user from JWT (`Authorization: Bearer <token>`)."""
    ip = _client_ip(request)
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        logger.warning("auth_failed ip=%s reason=jwt_expired", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.warning("auth_failed ip=%s reason=invalid_jwt", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
        ) from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        logger.warning("auth_failed ip=%s reason=jwt_missing_sub", ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user_id = int(sub)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        logger.warning("auth_failed ip=%s reason=user_not_found user_id=%s", ip, user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
