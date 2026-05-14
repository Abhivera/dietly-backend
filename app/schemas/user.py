from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, computed_field


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    height: Optional[int] = None
    goal_weight: Optional[int] = None


class StepGoalUpdate(BaseModel):
    step_goal: int = Field(..., ge=1000, le=100_000)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str = "user"
    gender: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    height: Optional[int] = None
    goal_weight: Optional[int] = None
    step_goal: int = 8000
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserStreakResponse(BaseModel):
    """Consecutive UTC calendar days with ≥1 `is_meal` image (steps do not affect streak)."""

    current_streak: int = Field(..., ge=0)
    longest_streak: int = Field(..., ge=0)
    last_logged_date: Optional[date] = None

    @computed_field
    @property
    def streak_days(self) -> int:
        return self.current_streak
