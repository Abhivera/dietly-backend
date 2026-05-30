from app.core.database import Database
from app.core.roles import UserRole
from app.models.user import User


def list_users(
    db: Database,
    *,
    skip: int = 0,
    limit: int = 100,
    email_contains: str | None = None,
) -> tuple[list[User], int]:
    return db.users.list_all(skip=skip, limit=limit, email_contains=email_contains)


def get_user_by_id(db: Database, user_id: str) -> User | None:
    return db.users.get_by_id(user_id)


def delete_user(db: Database, user_id: str) -> bool:
    user = get_user_by_id(db, user_id)
    if user is None:
        return False
    db.delete_user_cascade(user_id)
    return True


def set_user_role(db: Database, user_id: str, role: UserRole) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    user.role = role.value
    return db.users.save(user)


def patch_user_profile(db: Database, user_id: str, fields: dict) -> User | None:
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
    filtered = {k: v for k, v in fields.items() if k in allowed}
    return db.users.update_fields(user, filtered)
