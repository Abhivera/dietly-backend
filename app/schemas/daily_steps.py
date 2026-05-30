from datetime import date, datetime
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

StepSource = Literal["healthkit", "health_connect"]


class DailyStepDayIn(BaseModel):
    step_date: date
    step_count: int = Field(..., ge=0, le=200_000)
    distance_km: float | None = Field(None, ge=0, le=1000)
    source: StepSource


class DailyStepsSyncRequest(BaseModel):
    days: List[DailyStepDayIn] = Field(..., min_length=1, max_length=400)

    @field_validator("days", mode="after")
    @classmethod
    def unique_dates(cls, v: List[DailyStepDayIn]) -> List[DailyStepDayIn]:
        seen: set[date] = set()
        for d in v:
            if d.step_date in seen:
                raise ValueError(f"Duplicate step_date in payload: {d.step_date}")
            seen.add(d.step_date)
        return v


class DailyStepsResponse(BaseModel):
    id: str
    user_id: str
    step_date: date
    step_count: int
    distance_km: float | None
    kcal_burned: int
    source: str
    synced_at: datetime

    model_config = {"from_attributes": True}
