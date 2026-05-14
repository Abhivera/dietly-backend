"""Application RBAC roles (stored on `users.role`)."""

from enum import StrEnum


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


def is_admin(user: object) -> bool:
    return getattr(user, "role", None) == UserRole.admin.value
