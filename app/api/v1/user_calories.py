"""Authenticated **activity calories** (manual workout / burn logs by calendar day).

**Mobile+Web:** `POST /log-activity` is the quick structured log (walking, running, …) from native
shortcuts; `POST /` with full JSON list suits web forms or imports. Summaries feed dashboards.
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.user_calories import UserCalories, total_burned_from_json
from app.schemas.user_calories import (
    ActivityLogRequest,
    UserCaloriesCreate,
    UserCaloriesResponse,
    UserCaloriesSummary,
    UserCaloriesUpdate,
)
from app.services.activity_burn import activity_display_label, estimate_activity_calories

router = APIRouter()


def _activities_summary(calories_entries: List[UserCalories]) -> dict:
    summary: dict = {}
    for entry in calories_entries:
        if not entry.calories_burned:
            continue
        for activity in entry.calories_burned:
            name = activity.get("activity_name", "Unknown")
            try:
                cals = int(activity.get("calories", 0))
            except (ValueError, TypeError):
                continue
            summary[name] = summary.get(name, 0) + cals
    return summary


@router.post(
    "/",
    response_model=UserCaloriesResponse,
    summary="[Web+Mobile] Create full-day burn log (explicit activity list)",
    description="One row per `activity_date`; fails if a row already exists for that day.",
)
def create_user_calories(
    calories_data: UserCaloriesCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date == calories_data.activity_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Calorie entry already exists for date {calories_data.activity_date}",
        )
    activities_json = [a.model_dump() for a in calories_data.calories_burned]
    row = UserCalories(
        user_id=current_user.id,
        activity_date=calories_data.activity_date,
        calories_burned=activities_json,
        total_burned=total_burned_from_json(activities_json),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post(
    "/log-activity",
    response_model=UserCaloriesResponse,
    summary="[Mobile-first] Append one MET-based activity to a day",
    description="Creates the day row if needed; duplicates activity names get a numeric suffix.",
)
def log_structured_activity(
    body: ActivityLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    activity_date = body.activity_date or datetime.now(timezone.utc).date()
    weight_kg = float(current_user.weight) if current_user.weight and current_user.weight > 0 else None
    try:
        cals = estimate_activity_calories(
            body.activity_type,
            body.duration_minutes,
            weight_kg=weight_kg,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    base_label = activity_display_label(body.activity_type)
    base_name = f"{base_label} · {body.duration_minutes} min"

    row = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date == activity_date,
        )
        .first()
    )
    activities: list = []
    if row and row.calories_burned:
        activities = list(row.calories_burned)

    existing_names = {str(a.get("activity_name", "")) for a in activities}
    name = base_name
    suffix = 2
    while name in existing_names:
        name = f"{base_name} ({suffix})"
        suffix += 1

    current_total = 0
    for a in activities:
        try:
            current_total += int(a.get("calories", 0))
        except (ValueError, TypeError):
            continue
    if current_total + cals > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total daily calories burned cannot exceed 5000",
        )

    activities.append({"activity_name": name, "calories": str(cals)})

    total = total_burned_from_json(activities)

    if row:
        row.calories_burned = activities
        row.total_burned = total
        db.commit()
        db.refresh(row)
        return row

    new_row = UserCalories(
        user_id=current_user.id,
        activity_date=activity_date,
        calories_burned=activities,
        total_burned=total,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


@router.get(
    "/summary/range",
    response_model=UserCaloriesSummary,
    summary="[Mobile+Web] Burn totals over a custom date range",
)
def get_user_calories_summary(
    start_date: date = Query(..., description="Start date for summary"),
    end_date: date = Query(..., description="End date for summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before or equal to end date",
        )
    entries = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date >= start_date,
            UserCalories.activity_date <= end_date,
        )
        .all()
    )
    count = len(entries)
    total = 0
    for e in entries:
        total += e.total_burned
    avg = total / count if count else 0.0
    return UserCaloriesSummary(
        total_calories_burned=total,
        average_calories_per_day=avg,
        date_range_start=start_date,
        date_range_end=end_date,
        entries_count=count,
        activities_summary=_activities_summary(entries),
    )


@router.get(
    "/summary/recent",
    response_model=UserCaloriesSummary,
    summary="[Mobile+Web] Burn totals for the last N days",
)
def get_recent_calories_summary(
    days: int = Query(7, ge=1, le=365, description="Number of recent days to summarize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    entries = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date >= start_date,
            UserCalories.activity_date <= end_date,
        )
        .all()
    )
    count = len(entries)
    total = 0
    for e in entries:
        total += e.total_burned
    avg = total / count if count else 0.0
    return UserCaloriesSummary(
        total_calories_burned=total,
        average_calories_per_day=avg,
        date_range_start=start_date,
        date_range_end=end_date,
        entries_count=count,
        activities_summary=_activities_summary(entries),
    )


@router.get(
    "/",
    response_model=List[UserCaloriesResponse],
    summary="[Mobile+Web] List burn log rows (paginated, optional date bounds)",
)
def get_user_calories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(UserCalories).filter(UserCalories.user_id == current_user.id)
    if start_date:
        q = q.filter(UserCalories.activity_date >= start_date)
    if end_date:
        q = q.filter(UserCalories.activity_date <= end_date)
    return q.order_by(UserCalories.activity_date.desc()).offset(skip).limit(limit).all()


@router.get(
    "/date/{activity_date}",
    response_model=UserCaloriesResponse,
    summary="[Mobile+Web] Get one day’s burn log by calendar date",
)
def get_user_calories_by_date(
    activity_date: date,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date == activity_date,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calorie entry found for date {activity_date}",
        )
    return row


@router.get(
    "/{calories_id}",
    response_model=UserCaloriesResponse,
    summary="[Web+Mobile] Get burn log row by primary key",
    description="Use when you have the row `id` from a list response.",
)
def get_user_calories_by_id(
    calories_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserCalories)
        .filter(
            UserCalories.id == calories_id,
            UserCalories.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")
    return row


@router.put(
    "/{calories_id}",
    response_model=UserCaloriesResponse,
    summary="[Web+Mobile] Replace or shift fields on a burn log row",
)
def update_user_calories(
    calories_id: int,
    calories_update: UserCaloriesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    calories = (
        db.query(UserCalories)
        .filter(
            UserCalories.id == calories_id,
            UserCalories.user_id == current_user.id,
        )
        .first()
    )
    if not calories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")

    update_data = calories_update.model_dump(exclude_unset=True)
    if "activity_date" in update_data:
        conflict = (
            db.query(UserCalories)
            .filter(
                UserCalories.user_id == current_user.id,
                UserCalories.activity_date == update_data["activity_date"],
                UserCalories.id != calories_id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Calorie entry already exists for date {update_data['activity_date']}",
            )
    if "calories_burned" in update_data and update_data["calories_burned"] is not None:
        new_activities = []
        for activity in update_data["calories_burned"]:
            if hasattr(activity, "model_dump"):
                new_activities.append(activity.model_dump())
            elif isinstance(activity, dict):
                new_activities.append(activity)
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid activity format in calories_burned",
                )
        update_data["calories_burned"] = new_activities
    try:
        for field, value in update_data.items():
            setattr(calories, field, value)
        if "calories_burned" in update_data:
            calories.total_burned = total_burned_from_json(calories.calories_burned)
        db.commit()
        db.refresh(calories)
        return calories
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update calorie entry: {e}",
        ) from e


@router.delete(
    "/{calories_id}",
    summary="[Web+Mobile] Delete a burn log row",
)
def delete_user_calories(
    calories_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserCalories)
        .filter(
            UserCalories.id == calories_id,
            UserCalories.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")
    db.delete(row)
    db.commit()
    return {"success": True, "message": "Calorie entry deleted successfully"}
