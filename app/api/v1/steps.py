"""Authenticated **step charts** (dense calendar series for UI rings / graphs)."""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.database import Database, get_db
from app.models.user import User
from app.schemas.steps import StepsSummaryDayItem, StepsSummaryResponse

router = APIRouter()


@router.get("/summary", response_model=StepsSummaryResponse)
def steps_summary(
    end_date: date | None = Query(None, description="Inclusive end (UTC calendar day); defaults to today"),
    start_date: date | None = Query(None, description="Inclusive start; defaults to end_date (single day)"),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
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

    rows = db.daily_steps.list_for_user(
        current_user.id, start_date=start, end_date=end, limit=500
    )
    by_date = {r.step_date: r for r in rows}

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
