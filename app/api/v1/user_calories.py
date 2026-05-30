"""Authenticated **activity calories** (manual workout / burn logs by calendar day)."""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.database import Database, get_db
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


@router.post("/", response_model=UserCaloriesResponse, summary="[Web+Mobile] Create full-day burn log")
def create_user_calories(
    calories_data: UserCaloriesCreate,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    existing = db.user_calories.get(current_user.id, calories_data.activity_date)
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
    return db.user_calories.create(row)


@router.post("/log-activity", response_model=UserCaloriesResponse, summary="[Mobile-first] Append one activity")
def log_structured_activity(
    body: ActivityLogRequest,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
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

    row = db.user_calories.get(current_user.id, activity_date)
    activities: list = list(row.calories_burned) if row and row.calories_burned else []

    existing_names = {str(a.get("activity_name", "")) for a in activities}
    name = base_name
    suffix = 2
    while name in existing_names:
        name = f"{base_name} ({suffix})"
        suffix += 1

    current_total = sum(int(a.get("calories", 0)) for a in activities if str(a.get("calories", "")).isdigit())
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
        return db.user_calories.save(row)

    new_row = UserCalories(
        user_id=current_user.id,
        activity_date=activity_date,
        calories_burned=activities,
        total_burned=total,
    )
    return db.user_calories.create(new_row)


@router.get("/summary/range", response_model=UserCaloriesSummary)
def get_user_calories_summary(
    start_date: date = Query(..., description="Start date for summary"),
    end_date: date = Query(..., description="End date for summary"),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before or equal to end date",
        )
    entries = db.user_calories.list_for_user(
        current_user.id, start_date=start_date, end_date=end_date, limit=10_000
    )
    count = len(entries)
    total = sum(e.total_burned for e in entries)
    avg = total / count if count else 0.0
    return UserCaloriesSummary(
        total_calories_burned=total,
        average_calories_per_day=avg,
        date_range_start=start_date,
        date_range_end=end_date,
        entries_count=count,
        activities_summary=_activities_summary(entries),
    )


@router.get("/summary/recent", response_model=UserCaloriesSummary)
def get_recent_calories_summary(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    entries = db.user_calories.list_for_user(
        current_user.id, start_date=start_date, end_date=end_date, limit=10_000
    )
    count = len(entries)
    total = sum(e.total_burned for e in entries)
    avg = total / count if count else 0.0
    return UserCaloriesSummary(
        total_calories_burned=total,
        average_calories_per_day=avg,
        date_range_start=start_date,
        date_range_end=end_date,
        entries_count=count,
        activities_summary=_activities_summary(entries),
    )


@router.get("/", response_model=List[UserCaloriesResponse])
def get_user_calories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    return db.user_calories.list_for_user(
        current_user.id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.get("/date/{activity_date}", response_model=UserCaloriesResponse)
def get_user_calories_by_date(
    activity_date: date,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    row = db.user_calories.get(current_user.id, activity_date)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calorie entry found for date {activity_date}",
        )
    return row


@router.get("/{calories_id}", response_model=UserCaloriesResponse)
def get_user_calories_by_id(
    calories_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    row = db.user_calories.get_by_id(calories_id, current_user.id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")
    return row


@router.put("/{calories_id}", response_model=UserCaloriesResponse)
def update_user_calories(
    calories_id: str,
    calories_update: UserCaloriesUpdate,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    calories = db.user_calories.get_by_id(calories_id, current_user.id)
    if not calories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")

    update_data = calories_update.model_dump(exclude_unset=True)
    if "activity_date" in update_data:
        conflict = db.user_calories.get(current_user.id, update_data["activity_date"])
        if conflict and conflict.id != calories.id:
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

    old_date = calories.activity_date
    new_date = update_data.get("activity_date", old_date)

    for field, value in update_data.items():
        setattr(calories, field, value)
    if "calories_burned" in update_data:
        calories.total_burned = total_burned_from_json(calories.calories_burned)

    if new_date != old_date:
        db.user_calories.delete(UserCalories(user_id=calories.user_id, activity_date=old_date, calories_burned=[]))
        calories.activity_date = new_date
        calories.id = f"{calories.user_id}#{new_date.isoformat()}"

    return db.user_calories.save(calories)


@router.delete("/{calories_id}")
def delete_user_calories(
    calories_id: str,
    current_user: User = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    row = db.user_calories.get_by_id(calories_id, current_user.id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calorie entry not found")
    db.user_calories.delete(row)
    return {"success": True, "message": "Calorie entry deleted successfully"}
