"""**Unauthenticated** food image analysis (try-before-signup, marketing landing pages).

**Web-first / share:** no Firebase token; IP-based daily rate limit. **Mobile:** avoid for the
main app — use authenticated `POST /images/upload-and-analyze` so meals are saved to the user.
"""

import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from app.core.client_ip import get_client_ip
from app.core.config import settings
from app.core.meal_rules import infer_is_meal
from app.services.llm_service import LLMService
from app.utils.rate_limiter import check_daily_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze-food",
    summary="[Web-first] Analyze image without saving (rate limited)",
    description="Returns analysis JSON only; does not create `images` rows. See module docstring.",
)
async def analyze_food_image(
    request: Request,
    file: UploadFile = File(...),
    description: str | None = Form(None),
):
    try:
        limit = settings.public_analyze_daily_limit
        rate_limit_info = check_daily_rate_limit(request, max_requests=limit)

        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail="File must be an image (JPEG, PNG, GIF, WebP)",
            )

        content = await file.read()
        file_size = len(content)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Maximum file size is 10MB")

        try:
            img = Image.open(BytesIO(content))
            img.verify()
        except Exception as e:
            logger.warning(
                "public_image_validation_failed ip=%s error=%s",
                get_client_ip(request),
                e,
            )
            raise HTTPException(status_code=400, detail=f"Invalid image file: {e}") from e

        temp_file = None
        try:
            file_extension = Path(file.filename or "upload.jpg").suffix or ".jpg"
            temp_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
            temp_file.write(content)
            temp_file.close()

            llm_service = LLMService()
            analysis = await llm_service.analyze_image(temp_file.name, description=description)

            food_items = analysis.get("food_items", [])
            is_food = analysis.get("is_food", False)
            conf = analysis.get("confidence", 0.0)
            is_meal = infer_is_meal(is_food, conf, food_items)
            meal_name = analysis.get("meal_name") or None
            if isinstance(meal_name, str):
                meal_name = meal_name.strip() or None

            response = {
                "success": True,
                "analysis": {
                    "is_food": is_food,
                    "is_meal": is_meal,
                    "meal_name": meal_name,
                    "food_items": food_items,
                    "description": analysis.get("description", ""),
                    "calories": analysis.get("calories", 0),
                    "nutrients": analysis.get("nutrients", {}),
                    "confidence": conf,
                    "exercise_recommendations": {
                        "steps": int(analysis.get("calories", 0) * 20),
                        "walking_km": round(analysis.get("calories", 0) / 50, 2),
                    },
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                "rate_limit": {
                    "remaining_requests": rate_limit_info["remaining_requests"],
                    "limit": limit,
                    "period": "24 hours",
                },
            }
            if not analysis.get("is_food", False):
                response["analysis"]["note"] = "This image does not appear to contain food items."
            return response
        finally:
            if temp_file and Path(temp_file.name).exists():
                Path(temp_file.name).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception:
        ip = get_client_ip(request)
        logger.exception("public_food_analysis_failed ip=%s", ip)
        raise HTTPException(
            status_code=500,
            detail="Food analysis failed. Please try again later.",
        ) from None
