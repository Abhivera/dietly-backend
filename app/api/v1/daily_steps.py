"""Authenticated **raw step sync** (HealthKit / Health Connect style payloads)."""

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.database import Database, get_db
from app.models.daily_steps import DailySteps
from app.models.user import User
from app.schemas.daily_steps import DailyStepsResponse, DailyStepsSyncRequest
from app.services.activity_burn import estimate_steps_kcal_burned

router = APIRouter()


def _weight_kg(user: User) -> float | None:
    if user.weight is not None and user.weight > 0:
        return float(user.weight)
    return None


@router.post("/sync", response_model=List[DailyStepsResponse])
def sync_daily_steps(
    body: DailyStepsSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    w = _weight_kg(current_user)
    out: list[DailySteps] = []
    for day in body.days:
        if day.step_date > now.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"step_date cannot be in the future: {day.step_date}",
            )
        kcal = estimate_steps_kcal_burned(day.step_count, weight_kg=w)
        row = db.daily_steps.get(current_user.id, day.step_date)
        if row:
            row.step_count = day.step_count
            row.distance_km = day.distance_km
            row.kcal_burned = kcal
            row.source = day.source
            row.synced_at = now
        else:
            row = DailySteps(
                user_id=current_user.id,
                step_date=day.step_date,
                step_count=day.step_count,
                distance_km=day.distance_km,
                kcal_burned=kcal,
                source=day.source,
                synced_at=now,
            )
        out.append(db.daily_steps.upsert(row))
    return out


@router.get("/", response_model=List[DailyStepsResponse])
def list_daily_steps(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    return db.daily_steps.list_for_user(
        current_user.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.get("/{step_date}", response_model=DailyStepsResponse)
def get_daily_steps_for_date(
    step_date: date,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    row = db.daily_steps.get(current_user.id, step_date)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No step data for that date")
    return row
