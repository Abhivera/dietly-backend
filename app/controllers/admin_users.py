from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.models.user import User


def list_users(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    email_contains: str | None = None,
) -> tuple[list[User], int]:
    base = db.query(User)
    if email_contains:
        base = base.filter(User.email.ilike(f"%{email_contains}%"))
    total = base.count()
    rows = base.order_by(User.id).offset(skip).limit(limit).all()
    return rows, total


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def delete_user(db: Session, user_id: int) -> bool:
    user = get_user_by_id(db, user_id)
    if user is None:
        return False
    db.delete(user)
    db.commit()
    return True


def set_user_role(db: Session, user_id: int, role: UserRole) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    user.role = role.value
    db.commit()
    db.refresh(user)
    return user


def patch_user_profile(db: Session, user_id: int, fields: dict) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    allowed = {
        "full_name",
        "avatar_url",
        "gender",
        "age",
        "weight",
        "height",
        "goal_weight",
        "step_goal",
    }
    for key, value in fields.items():
        if key in allowed:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
