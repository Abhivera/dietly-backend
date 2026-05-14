from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class StepsSummaryDayItem(BaseModel):
    """One calendar day; zeros when no `daily_steps` row (e.g. web-only users)."""

    date: date
    steps: int = Field(0, ge=0)
    kcal_burned: int = Field(0, ge=0)
    distance_km: float = Field(0.0, ge=0)
    source: Optional[str] = None


class StepsSummaryResponse(BaseModel):
    days: list[StepsSummaryDayItem]
