"""Authenticated **raw step sync** (HealthKit / Health Connect style payloads).

**Mobile-first:** batch `POST /sync` from wearable SDKs. **Web:** rarely used; charts should prefer
`GET /steps/summary` which zero-fills missing days for web-only users.
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.daily_steps import DailySteps
from app.models.user import User
from app.schemas.daily_steps import DailyStepsResponse, DailyStepsSyncRequest
from app.services.activity_burn import estimate_steps_kcal_burned

router = APIRouter()


def _weight_kg(user: User) -> float | None:
    if user.weight is not None and user.weight > 0:
        return float(user.weight)
    return None


@router.post(
    "/sync",
    response_model=List[DailyStepsResponse],
    summary="[Mobile-first] Upsert daily step rows (batch)",
    description="Recomputes `kcal_burned` from `users.weight` per day; sets `synced_at` to now.",
)
def sync_daily_steps(
    body: DailyStepsSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        row = (
            db.query(DailySteps)
            .filter(
                DailySteps.user_id == current_user.id,
                DailySteps.step_date == day.step_date,
            )
            .first()
        )
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
            db.add(row)
        out.append(row)
    db.commit()
    for r in out:
        db.refresh(r)
    return out


@router.get(
    "/",
    response_model=List[DailyStepsResponse],
    summary="[Mobile+Web] List stored daily step rows (sparse)",
    description="Only dates that have been synced appear; use `/steps/summary` for a continuous range.",
)
def list_daily_steps(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(DailySteps).filter(DailySteps.user_id == current_user.id)
    if start_date:
        q = q.filter(DailySteps.step_date >= start_date)
    if end_date:
        q = q.filter(DailySteps.step_date <= end_date)
    return q.order_by(DailySteps.step_date.desc()).offset(skip).limit(limit).all()


@router.get(
    "/{step_date}",
    response_model=DailyStepsResponse,
    summary="[Mobile+Web] Single day raw row",
    description="404 if no sync for that date; prefer `/steps/summary` when the UI needs zeros.",
)
def get_daily_steps_for_date(
    step_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(DailySteps)
        .filter(
            DailySteps.user_id == current_user.id,
            DailySteps.step_date == step_date,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No step data for that date")
    return row
