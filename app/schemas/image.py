from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class ExerciseRecommendations(BaseModel):
    steps: int = 0
    walking_km: float = 0

class ImageBase(BaseModel):
    original_filename: str

class ImageCreate(ImageBase):
    filename: str
    file_url: str
    s3_key: str
    s3_bucket: str
    file_size: int
    content_type: str

class ImageUpdate(BaseModel):
    description: Optional[str] = None
    tags: Optional[str] = None

class ImageInDB(ImageBase):
    id: int
    filename: str
    file_url: str
    s3_key: str
    s3_bucket: str
    file_size: int
    content_type: str
    description: Optional[str] = None
    tags: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    is_food: Optional[bool] = None
    is_meal: Optional[bool] = False
    analysis_description: Optional[str] = None
    food_items: Optional[List[str]] = None
    estimated_calories: Optional[int] = None
    nutrients: Optional[Dict[str, Any]] = None
    analysis_confidence: Optional[float] = None
    analysis_completed: Optional[datetime] = None
    meal_name: Optional[str] = None

    class Config:
        from_attributes = True

class ImageResponse(ImageInDB):
    analysis: Optional[Dict[str, Any]] = None

class ImageAnalysisResponse(BaseModel):
    description: str
    tags: List[str]
    confidence: float

class ImageAnalysisData(BaseModel):
    """Analysis data structure"""
    is_food: bool
    is_meal: bool = False
    meal_name: Optional[str] = None
    food_items: List[str]
    description: str
    calories: int
    nutrients: Dict[str, Any]
    confidence: float
    exercise_recommendations: ExerciseRecommendations = ExerciseRecommendations()

class ImageUploadResponse(BaseModel):
    """Response for image upload"""
    success: bool
    image_id: int
    file_url: str
    analysis: ImageAnalysisData

class ImageListResponse(BaseModel):
    """Response for listing images"""
    images: List[ImageResponse]
    total: int
    skip: int
    limit: int