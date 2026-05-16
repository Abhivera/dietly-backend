"""Authenticated **current user** (`/me`) — shared by native mobile and web clients.

**Mobile:** streak, net-calories, step-goal, and avatar are typical home / settings flows (camera
gallery for avatar). **Web:** same contracts; omit step UI if the user has no wearable sync.

Route summaries use **[Mobile+Web]** (both), **[Mobile-first]** (mainly native), or **[Web+Mobile]**.
"""

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.daily_steps import DailySteps
from app.models.image import Image
from app.models.user import User
from app.models.user_calories import UserCalories
from app.schemas.net_calories import NetCaloriesResponse
from app.schemas.user import StepGoalUpdate, UserResponse, UserStreakResponse, UserUpdate
from app.services.media_storage import MediaStorageService
from app.services.streak_service import sync_user_streak

router = APIRouter()


@router.get(
    "/me/net-calories",
    response_model=NetCaloriesResponse,
    summary="[Mobile+Web] Net calories for a UTC calendar day",
    description=(
        "Eaten (meal images) minus manual burns and optional step-derived kcal; "
        "`daily_steps` missing for that day contributes 0 (web-only users)."
    ),
)
def read_user_me_net_calories(
    target_date: date | None = Query(None, alias="date", description="UTC calendar day; defaults to today"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = target_date if target_date is not None else datetime.now(timezone.utc).date()
    today = datetime.now(timezone.utc).date()
    if d > today:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date cannot be in the future")

    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    eaten = (
        db.query(func.coalesce(func.sum(func.coalesce(Image.estimated_calories, 0)), 0))
        .filter(
            Image.owner_id == current_user.id,
            Image.is_meal.is_(True),
            Image.created_at.isnot(None),
            Image.created_at >= start,
            Image.created_at < end,
        )
        .scalar()
    )
    calories_eaten = int(eaten or 0)

    uc = (
        db.query(UserCalories)
        .filter(
            UserCalories.user_id == current_user.id,
            UserCalories.activity_date == d,
        )
        .first()
    )
    manual = int(uc.total_burned) if uc else 0

    ds = (
        db.query(DailySteps)
        .filter(
            DailySteps.user_id == current_user.id,
            DailySteps.step_date == d,
        )
        .first()
    )
    steps_kcal = int(ds.kcal_burned) if ds else 0

    burned_total = manual + steps_kcal
    net = calories_eaten - burned_total

    return NetCaloriesResponse(
        date=d,
        calories_eaten=calories_eaten,
        calories_burned_manual=manual,
        calories_burned_steps=steps_kcal,
        calories_burned_total=burned_total,
        net_calories=net,
    )


@router.get(
    "/me/streak",
    response_model=UserStreakResponse,
    summary="[Mobile+Web] Meal logging streak",
    description="Consecutive UTC days with ≥1 `is_meal` image; steps do not affect streak.",
)
def read_user_me_streak(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = sync_user_streak(db, current_user.id)
    return UserStreakResponse(
        current_streak=row.current_streak,
        longest_streak=row.longest_streak,
        last_logged_date=row.last_logged_date,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="[Mobile+Web] Current user profile",
)
def read_user_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    summary="[Mobile+Web] Update profile fields",
    description="Body metrics and display name; not for email or password (use auth endpoints).",
)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch(
    "/me/step-goal",
    response_model=UserResponse,
    summary="[Mobile-first] Daily step target",
    description="Used with HealthKit / Health Connect flows; web clients may hide if unused.",
)
def patch_user_step_goal(
    body: StepGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.step_goal = body.step_goal
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="[Mobile+Web] Upload profile photo",
    description="Multipart image upload; file is saved under UPLOAD_DIR and served via /media.",
)
def upload_user_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )
    storage = MediaStorageService()
    file_content = file.file.read()
    from io import BytesIO

    file_obj = BytesIO(file_content)
    upload_result = storage.upload_file_with_public_access(
        file_obj, str(current_user.id), file.filename or "avatar.jpg"
    )
    if not upload_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=upload_result.get("error", "Upload failed"),
        )
    current_user.avatar_url = upload_result["file_url"]
    db.commit()
    db.refresh(current_user)
    return current_user
