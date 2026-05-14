from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_url = Column(String(500), nullable=False)
    s3_key = Column(String(255), nullable=False)
    s3_bucket = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    is_food = Column(Boolean, nullable=True)
    is_meal = Column(Boolean, nullable=True, default=False)
    analysis_description = Column(Text, nullable=True)
    food_items = Column(JSON, nullable=True)
    estimated_calories = Column(Integer, nullable=True)
    nutrients = Column(JSON, nullable=True)
    analysis_confidence = Column(Float, nullable=True)
    analysis_completed = Column(DateTime(timezone=True), nullable=True)
    meal_name = Column(String(255), nullable=True)

    presigned_url = Column(String(1000), nullable=True)
    presigned_url_expires_at = Column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="images")

    def to_dict(self):
        calories = self.estimated_calories or 0
        exercise_recommendations = {"steps": int(calories * 20), "walking_km": round(calories / 50, 2)}
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
