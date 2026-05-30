"""Authenticated **meal aggregates** (calories and exercise hints from logged meals).

**Mobile+Web:** dashboard charts and day/week/month views. Data comes from stored image analysis
(`is_meal` only), not live LLM calls.
"""

from typing import Any, Dict, Optional

import logging

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import Database, get_db
from app.models.user import User
from app.services.image_service import ImageService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/",
    summary="[Mobile+Web] Meal / calorie / exercise summary for a period",
    description="Query one of: `date` (YYYY-MM-DD), `week` (YYYY-Www), or `month` (YYYY-MM).",
    tags=["meal"],
)
async def get_meal_summary(
    date: Optional[str] = None,
    week: Optional[str] = None,
    month: Optional[str] = None,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Only `analysis.is_meal` images are included in totals and `meals` list."""
    try:
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
                current_user.id, 0, 10000, filter_type, filter_value
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        meal_images = [img for img in images if img.get("analysis", {}).get("is_meal")]
        total_meals = len(meal_images)
        total_calories = sum(img.get("analysis", {}).get("calories", 0) or 0 for img in meal_images)
        total_steps = sum(
            img.get("analysis", {}).get("exercise_recommendations", {}).get("steps", 0) or 0
            for img in meal_images
        )
        total_km = sum(
            img.get("analysis", {}).get("exercise_recommendations", {}).get("walking_km", 0) or 0
            for img in meal_images
        )
        return {
            "total_meals": total_meals,
            "total_calories": total_calories,
            "total_exercise": {"steps": total_steps, "walking_km": total_km},
            "meals": meal_images,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "meal_summary_failed user_id=%s date=%s week=%s month=%s",
            current_user.id,
            date,
            week,
            month,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve meal summary. Please try again later.",
        ) from None
