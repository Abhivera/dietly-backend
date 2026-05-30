from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.db.serialize import from_dynamo, from_iso, to_dynamo, to_iso, utc_now


@dataclass
class Image:
    id: str
    filename: str
    original_filename: str
    file_url: str
    s3_key: str
    s3_bucket: str
    file_size: int
    content_type: str
    owner_id: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None
    description: str | None = None
    tags: str | None = None
    is_food: bool | None = None
    is_meal: bool | None = False
    analysis_description: str | None = None
    food_items: list | None = None
    estimated_calories: int | None = None
    nutrients: dict | None = None
    analysis_confidence: float | None = None
    analysis_completed: datetime | None = None
    meal_name: str | None = None
    presigned_url: str | None = None
    presigned_url_expires_at: datetime | None = None

    @classmethod
    def new(cls, **kwargs: Any) -> Image:
        return cls(id=str(uuid4()), **kwargs)

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_url": self.file_url,
            "s3_key": self.s3_key,
            "s3_bucket": self.s3_bucket,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "owner_id": self.owner_id,
            "created_at": to_iso(self.created_at),
        }
        optional = {
            "updated_at": to_iso(self.updated_at),
            "description": self.description,
            "tags": self.tags,
            "is_food": self.is_food,
            "is_meal": self.is_meal,
            "analysis_description": self.analysis_description,
            "food_items": self.food_items,
            "estimated_calories": self.estimated_calories,
            "nutrients": self.nutrients,
            "analysis_confidence": self.analysis_confidence,
            "analysis_completed": to_iso(self.analysis_completed),
            "meal_name": self.meal_name,
            "presigned_url": self.presigned_url,
            "presigned_url_expires_at": to_iso(self.presigned_url_expires_at),
        }
        for key, value in optional.items():
            if value is not None:
                item[key] = value
        return to_dynamo(item)

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> Image:
        data = from_dynamo(item)
        return cls(
            id=data["id"],
            filename=data["filename"],
            original_filename=data["original_filename"],
            file_url=data["file_url"],
            s3_key=data["s3_key"],
            s3_bucket=data["s3_bucket"],
            file_size=int(data["file_size"]),
            content_type=data["content_type"],
            owner_id=data["owner_id"],
            created_at=from_iso(data["created_at"]) or utc_now(),
            updated_at=from_iso(data.get("updated_at")),
            description=data.get("description"),
            tags=data.get("tags"),
            is_food=data.get("is_food"),
            is_meal=data.get("is_meal", False),
            analysis_description=data.get("analysis_description"),
            food_items=data.get("food_items"),
            estimated_calories=data.get("estimated_calories"),
            nutrients=data.get("nutrients"),
            analysis_confidence=data.get("analysis_confidence"),
            analysis_completed=from_iso(data.get("analysis_completed")),
            meal_name=data.get("meal_name"),
            presigned_url=data.get("presigned_url"),
            presigned_url_expires_at=from_iso(data.get("presigned_url_expires_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        calories = self.estimated_calories or 0
        exercise_recommendations = {
            "steps": int(calories * 20),
            "walking_km": round(calories / 50, 2),
        }
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_url": self.file_url,
            "s3_key": self.s3_key,
            "s3_bucket": self.s3_bucket,
            "file_size": self.file_size,
            "content_type": self.content_type,
            "description": self.description,
            "tags": self.tags,
            "owner_id": self.owner_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "analysis": {
                "is_food": self.is_food,
                "is_meal": self.is_meal,
                "meal_name": self.meal_name,
                "food_items": self.food_items or [],
                "description": self.analysis_description,
                "calories": self.estimated_calories,
                "nutrients": self.nutrients or {},
                "confidence": self.analysis_confidence,
                "completed_at": self.analysis_completed.isoformat() if self.analysis_completed else None,
                "exercise_recommendations": exercise_recommendations,
            },
        }
