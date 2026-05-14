from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.roles import UserRole
from app.models.image import Image
from app.models.user import User


def get_admin_stats(db: Session) -> dict[str, int]:
    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    admin_users = int(
        db.query(func.count(User.id)).filter(User.role == UserRole.admin.value).scalar() or 0
    )
    total_images = int(db.query(func.count(Image.id)).scalar() or 0)
    return {
        "total_users": total_users,
        "admin_users": admin_users,
        "total_images": total_images,
    }
