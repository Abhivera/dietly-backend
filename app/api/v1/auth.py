import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.api.deps import get_firebase_claims
from app.core.config import settings
from app.core.database import Database, get_db
from app.core.roles import UserRole
from app.models.user import User
from app.schemas.auth import SessionBody
from app.schemas.user import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _email_from_claims(claims: dict[str, object]) -> str:
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase account must have a verified email",
        )
    return email.lower().strip()


def _uid_from_claims(claims: dict[str, object]) -> str:
    uid = claims.get("uid") or claims.get("sub")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return uid


def _name_from_claims(claims: dict[str, object]) -> str | None:
    name = claims.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


@router.post("/session", response_model=UserResponse, status_code=status.HTTP_200_OK)
def sync_session(
    body: SessionBody = Body(default_factory=SessionBody),
    claims: dict[str, object] = Depends(get_firebase_claims),
    db: Database = Depends(get_db),
):
    """Create or link a Calovia user for the signed-in Firebase account."""
    firebase_uid = _uid_from_claims(claims)
    email = _email_from_claims(claims)

    user = db.users.get_by_firebase_uid_or_email(firebase_uid, email)

    if user is not None:
        changed = False
        if user.firebase_uid is None:
            user.firebase_uid = firebase_uid
            changed = True
        if user.email != email:
            user.email = email
            changed = True
        if body.full_name and body.full_name.strip():
            user.full_name = body.full_name.strip()
            changed = True
        elif not user.full_name:
            claim_name = _name_from_claims(claims)
            if claim_name:
                user.full_name = claim_name
                changed = True
        if changed:
            db.users.save(user)
        return user

    display_name = (
        (body.full_name.strip() if body.full_name else None)
        or _name_from_claims(claims)
        or email.split("@")[0]
    )
    user = User.new(
        email=email,
        firebase_uid=firebase_uid,
        password_hash=None,
        full_name=display_name,
        avatar_url=settings.default_avatar_url,
        role=UserRole.user.value,
    )
    try:
        db.users.create(user)
    except Exception:
        logger.exception("firebase_session_failed email=%s uid=%s", email, firebase_uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create account",
        ) from None

    return user
