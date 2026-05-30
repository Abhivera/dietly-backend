from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.roles import UserRole
from app.schemas.user import UserResponse


class AdminRoleUpdate(BaseModel):
    role: UserRole = Field(..., description="New role for the user")


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int = Field(..., ge=0)
    skip: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)


class AdminUserImagesListResponse(BaseModel):
    user_id: str
    total: int = Field(..., ge=0)
    images: list[dict[str, Any]]


class AdminUserProfilePatch(BaseModel):
    """Support edits only — does not change `email`, password hash, or `role` (use PATCH .../role)."""

    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    gender: Optional[str] = Field(None, max_length=32)
    age: Optional[int] = Field(None, ge=0, le=130)
    weight: Optional[int] = Field(None, ge=0, le=500)
    height: Optional[int] = Field(None, ge=0, le=300)
    goal_weight: Optional[int] = Field(None, ge=0, le=500)
    step_goal: Optional[int] = Field(None, ge=1000, le=100_000)


class AdminStatsResponse(BaseModel):
    total_users: int = Field(..., ge=0)
    admin_users: int = Field(..., ge=0)
    total_images: int = Field(..., ge=0)
