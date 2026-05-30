from app.core.database import Database
from app.core.roles import UserRole


def get_admin_stats(db: Database) -> dict[str, int]:
    return {
        "total_users": db.users.count_all(),
        "admin_users": db.users.count_by_role(UserRole.admin.value),
        "total_images": db.images.count_all(),
    }
