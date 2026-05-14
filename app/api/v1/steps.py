"""Authenticated **step charts** (dense calendar series for UI rings / graphs).

**Mobile+Web:** `GET /summary` returns every day in the requested UTC range with **zeros** when no
`daily_steps` row exists (web-only users). Pair with `POST /daily-steps/sync` on mobile.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.daily_steps import DailySteps
from app.models.user import User
from app.schemas.steps import StepsSummaryDayItem, StepsSummaryResponse

router = APIRouter()


@router.get(
    "/summary",
    response_model=StepsSummaryResponse,
    summary="[Mobile+Web] Dense per-day steps and kcal for charts",
    description="Every calendar day in range is present; missing DB rows use steps=0, kcal_burned=0.",
)
def steps_summary(
    end_date: date | None = Query(None, description="Inclusive end (UTC calendar day); defaults to today"),
    start_date: date | None = Query(None, description="Inclusive start; defaults to end_date (single day)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    end = end_date if end_date is not None else today
    start = start_date if start_date is not None else end
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date",
        )
    if (end - start).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 367 days",
        )
    if end > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date cannot be in the future",
        )

    rows = (
        db.query(DailySteps)
        .filter(
            DailySteps.user_id == current_user.id,
            DailySteps.step_date >= start,
            DailySteps.step_date <= end,
        )
        .all()
    )
    by_date: dict[date, DailySteps] = {r.step_date: r for r in rows}

    days: list[StepsSummaryDayItem] = []
    d = start
    while d <= end:
        r = by_date.get(d)
        if r is None:
            days.append(StepsSummaryDayItem(date=d))
        else:
            days.append(
                StepsSummaryDayItem(
                    date=d,
                    steps=r.step_count,
                    kcal_burned=r.kcal_burned,
                    distance_km=float(r.distance_km or 0.0),
                    source=r.source,
                )
            )
        d += timedelta(days=1)

    return StepsSummaryResponse(days=days)
