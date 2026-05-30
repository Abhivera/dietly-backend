from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

ActivityType = Literal[
    "walking",
    "running",
    "cycling",
    "swimming",
    "yoga",
    "strength_training",
]


class ActivityLogRequest(BaseModel):
    """Structured activity log; calories burned are computed server-side (MET × weight × duration)."""

    activity_type: ActivityType
    duration_minutes: int = Field(ge=1, le=480)
    activity_date: Optional[date] = Field(
        None,
        description="Calendar day for the log; defaults to today (UTC)",
    )

    @field_validator("activity_date", mode="after")
    @classmethod
    def no_future_log(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        from datetime import timezone

        today = datetime.now(timezone.utc).date()
        if v > today:
            raise ValueError("Activity date cannot be in the future")
        return v


class ActivityCalories(BaseModel):
    activity_name: str = Field(..., min_length=1, max_length=100)
    calories: str = Field(..., description="Calories burned for this activity")

    @field_validator("activity_name", mode="after")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Activity name cannot be empty")
        if len(v.strip()) > 100:
            raise ValueError("Activity name cannot exceed 100 characters")
        return v.strip()

    @field_validator("calories", mode="after")
    @classmethod
    def validate_calories(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Calories value cannot be empty")
        try:
            n = int(v)
        except ValueError as e:
            raise ValueError("Calories must be a valid number") from e
        if n < 0:
            raise ValueError("Calories cannot be negative")
        if n > 10000:
            raise ValueError("Calories value seems too high (max 10000)")
        return v


class UserCaloriesBase(BaseModel):
    activity_date: date
    calories_burned: List[ActivityCalories] = Field(
        ...,
        description="List of activities with calories burned",
    )

    @field_validator("calories_burned", mode="after")
    @classmethod
    def validate_burned(cls, v: List[ActivityCalories]) -> List[ActivityCalories]:
        if not v:
            raise ValueError("At least one activity must be provided")
        names = [a.activity_name.lower() for a in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate activity names are not allowed")
        total = sum(int(a.calories) for a in v)
        if total > 5000:
            raise ValueError("Total daily calories burned cannot exceed 5000")
        return v

    @field_validator("activity_date", mode="after")
    @classmethod
    def no_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Activity date cannot be in the future")
        return v


class UserCaloriesCreate(UserCaloriesBase):
    pass


class UserCaloriesUpdate(BaseModel):
    activity_date: Optional[date] = None
    calories_burned: Optional[List[ActivityCalories]] = None

    @field_validator("calories_burned", mode="after")
    @classmethod
    def validate_burned_update(cls, v: Optional[List[ActivityCalories]]) -> Optional[List[ActivityCalories]]:
        if v is None:
            return v
        if not v:
            raise ValueError("At least one activity must be provided")
        names = [a.activity_name.lower() for a in v]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate activity names are not allowed")
        total = sum(int(a.calories) for a in v)
        if total > 5000:
            raise ValueError("Total daily calories burned cannot exceed 5000")
        return v

    @field_validator("activity_date", mode="after")
    @classmethod
    def no_future_update(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("Activity date cannot be in the future")
        return v


class UserCaloriesResponse(BaseModel):
    id: str
    user_id: str
    activity_date: date
    calories_burned: List[Dict[str, Any]]
    total_burned: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserCaloriesSummary(BaseModel):
    total_calories_burned: int
    average_calories_per_day: float
    date_range_start: date
    date_range_end: date
    entries_count: int
    activities_summary: Dict[str, int] = Field(
        ...,
        description="Summary of calories by activity type",
    )
