"""Authenticated **food images** — camera capture, gallery, and meal history.

**Mobile-first:** `POST /upload-and-analyze` (multipart + optional caption) is the primary log-meal
flow. **Web+Mobile:** list, detail, presigned URL refresh, `is_meal` correction, relog.

**Dev only:** `POST /test-llm`, `POST /{image_id}/test` — diagnostics, not part of the main client flow.
"""

import logging
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image as PILImage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.client_ip import get_client_ip
from app.core.database import get_db
from app.models.image import Image
from app.models.user import User
from app.services.image_service import ImageService
from app.services.llm_service import LLMService

router = APIRouter()
logger = logging.getLogger(__name__)


class IsMealUpdateRequest(BaseModel):
    is_meal: bool


@router.post(
    "/upload-and-analyze",
    summary="[Mobile-first] Log meal from photo + run vision analysis",
    description="Multipart image; optional `description` form field. Main native logging path.",
)
async def upload_and_analyze_image(
    request: Request,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = getattr(request.state, "client_ip", None) or get_client_ip(request)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    content = await file.read()
    file_size = len(content)
    try:
        img = PILImage.open(BytesIO(content))
        img.verify()
    except Exception as e:
        logger.warning("image_validation_failed ip=%s user_id=%s error=%s", ip, current_user.id, e)
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}") from e

    file_obj = BytesIO(content)
    image_service = ImageService(db)
    result = await image_service.upload_and_analyze_image(
        file_obj=file_obj,
        original_filename=file.filename or "upload.jpg",
        file_size=file_size,
        content_type=file.content_type,
        user_id=current_user.id,
        user_description=description,
    )
    if "error" in result:
        logger.error(
            "upload_and_analyze_failed ip=%s user_id=%s error=%s",
            ip,
            current_user.id,
            result["error"],
        )
        raise HTTPException(
            status_code=503,
            detail="Image upload or analysis is temporarily unavailable. Please try again later.",
        )
    if description:
        result["user_description"] = description
    return result


@router.get(
    "",
    summary="[Mobile+Web] Paginated meal/photo history",
    description="Optional `date`, `week`, or `month` filter (same semantics as meal summary).",
)
async def get_user_images(
    skip: int = 0,
    limit: int = 20,
    date: str | None = None,
    week: str | None = None,
    month: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filter_type = None
    filter_value = None
    if date:
        filter_type, filter_value = "date", date
    elif week:
        filter_type, filter_value = "week", week
    elif month:
        filter_type, filter_value = "month", month
    image_service = ImageService(db)
    try:
        images = image_service.get_user_images_with_analysis(
            current_user.id, skip, limit, filter_type, filter_value
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"images": images, "total": len(images), "skip": skip, "limit": limit}


@router.get(
    "/{image_id}/suggested-name",
    summary="[Mobile+Web] Persisted LLM meal title",
    description="Reads stored `meal_name` from last analysis — no extra model call.",
)
async def get_suggested_meal_name(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    result = image_service.get_suggested_meal_name(image_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    return result


@router.post(
    "/{image_id}/relog",
    summary="[Mobile-first] Duplicate meal log (same file, new row)",
    description="Quick re-log of a previous meal without re-uploading the file.",
)
async def relog_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    result = image_service.relog_image(image_id, current_user.id)
    if "error" in result:
        code = 404 if "not found" in result["error"].lower() else 400
        raise HTTPException(status_code=code, detail=result["error"])
    return result


@router.get(
    "/{image_id}",
    summary="[Mobile+Web] Single image with analysis payload",
)
async def get_image_with_analysis(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    result = image_service.get_image_with_analysis(image_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    return result


@router.get(
    "/{image_id}/fresh-url",
    summary="[Mobile+Web] Refresh private image URL",
    description="Returns presigned URL when bucket objects are not public; use before displaying old rows.",
)
async def get_image_with_fresh_url(
    image_id: int,
    expiration: int = 3600,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    result = image_service.get_image_with_presigned_url(image_id, current_user.id, expiration)
    if not result:
        raise HTTPException(status_code=404, detail="Image not found")
    return result


@router.delete(
    "/{image_id}",
    summary="[Mobile+Web] Delete my image",
)
async def delete_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    result = image_service.delete_image(image_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post(
    "/{image_id}/test",
    summary="[Dev only] Storage + LLM smoke test for one image",
    description="Diagnostics for local use; omit from shipped mobile/web clients.",
)
async def test_image_processing(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_service = ImageService(db)
    return await image_service.test_storage_and_analysis(image_id, current_user.id)


@router.post(
    "/test-llm",
    summary="[Dev only] LLM provider connectivity",
    description="Verifies configured vision provider; not a product feature.",
)
async def test_llm_service(current_user: User = Depends(get_current_user)):
    llm_service = LLMService()
    result = await llm_service.test_api_connection()
    return {
        "success": result,
        "message": "LLM service is working" if result else "LLM service test failed",
    }


@router.patch(
    "/is-meal/{image_id}",
    summary="[Mobile+Web] Toggle whether image counts as a meal",
    description="Only allowed when `is_food` is true; adjusts streak and meal summaries.",
)
async def update_is_meal(
    image_id: int,
    req: IsMealUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = (
        db.query(Image)
        .filter(
            Image.id == image_id,
            Image.owner_id == current_user.id,
        )
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not image.is_food:
        raise HTTPException(status_code=400, detail="Cannot set is_meal: image is not food")
    image.is_meal = req.is_meal
    db.commit()
    db.refresh(image)
    return {"success": True, "image_id": image.id, "is_meal": image.is_meal}
