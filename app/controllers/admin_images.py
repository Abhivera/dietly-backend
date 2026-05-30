import logging

from app.core.database import Database
from app.services.image_service import ImageService
from app.services.media_storage import MediaStorageService
from app.services.streak_service import sync_user_streak

logger = logging.getLogger(__name__)


def list_images_for_user(db: Database, user_id: str) -> list[dict]:
    service = ImageService(db)
    return service.get_user_images_with_analysis(user_id, skip=0, limit=10000)


def get_image_detail_for_admin(db: Database, image_id: str) -> dict | None:
    img = db.images.get_by_id(image_id)
    if img is None:
        return None
    service = ImageService(db)
    return service.get_image_with_analysis(image_id, img.owner_id)


def delete_image_by_id(db: Database, image_id: str) -> tuple[bool, str]:
    """Delete stored file and DB row. Returns (ok, error_code_or_empty)."""
    image = db.images.get_by_id(image_id)
    if image is None:
        return False, "not_found"
    owner_id = image.owner_id
    storage = MediaStorageService()
    try:
        if not storage.delete_file(image.s3_key):
            return False, "storage_failed"
        db.images.delete(image)
    except Exception:
        logger.exception("admin_delete_image failed image_id=%s", image_id)
        return False, "delete_failed"
    try:
        sync_user_streak(db, owner_id)
    except Exception:
        logger.exception("sync_user_streak after admin image delete user_id=%s", owner_id)
    return True, ""
