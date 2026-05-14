import logging

from sqlalchemy.orm import Session

from app.models.image import Image
from app.services.image_service import ImageService
from app.services.s3_service import S3Service
from app.services.streak_service import sync_user_streak

logger = logging.getLogger(__name__)


def list_images_for_user(db: Session, user_id: int) -> list[dict]:
    service = ImageService(db)
    return service.get_user_images_with_analysis(user_id, skip=0, limit=10000)


def get_image_detail_for_admin(db: Session, image_id: int) -> dict | None:
    img = db.query(Image).filter(Image.id == image_id).first()
    if img is None:
        return None
    service = ImageService(db)
    return service.get_image_with_analysis(image_id, img.owner_id)


def delete_image_by_id(db: Session, image_id: int) -> tuple[bool, str]:
    """Delete any image by id (S3 + row). Returns (ok, error_code_or_empty)."""
    image = db.query(Image).filter(Image.id == image_id).first()
    if image is None:
        return False, "not_found"
    owner_id = image.owner_id
    s3 = S3Service()
    try:
        if not s3.delete_file(image.s3_key):
            return False, "s3_failed"
        db.delete(image)
        db.commit()
    except Exception:
        logger.exception("admin_delete_image failed image_id=%s", image_id)
        db.rollback()
        return False, "delete_failed"
    try:
        sync_user_streak(db, owner_id)
    except Exception:
        logger.exception("sync_user_streak after admin image delete user_id=%s", owner_id)
    return True, ""
