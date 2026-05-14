from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.controllers import admin_stats as admin_stats_ctrl
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import AdminStatsResponse

router = APIRouter()


@router.get("", response_model=AdminStatsResponse, summary="Aggregate counts for dashboard")
def admin_stats(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    data = admin_stats_ctrl.get_admin_stats(db)
    return AdminStatsResponse(**data)
