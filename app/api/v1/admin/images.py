from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_admin
from app.controllers import admin_images as admin_images_ctrl
from app.core.database import Database, get_db
from app.models.user import User

router = APIRouter()


@router.get("/{image_id}", summary="Get one image with analysis (any owner)")
def admin_get_image(
    image_id: str,
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    detail = admin_images_ctrl.get_image_detail_for_admin(db, image_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return detail


@router.delete("/{image_id}", summary="Delete an image (file on disk + DB, any owner)")
def admin_delete_image(
    image_id: str,
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    ok, err = admin_images_ctrl.delete_image_by_id(db, image_id)
    if not ok:
        if err == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
        if err == "storage_failed":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not delete object from storage",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Delete failed")
    return {"success": True, "message": f"Image {image_id} deleted."}
