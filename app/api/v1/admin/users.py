from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_admin
from app.controllers import admin_users as admin_users_ctrl
from app.controllers import admin_images as admin_images_ctrl
from app.core.database import Database, get_db
from app.core.roles import UserRole
from app.models.user import User
from app.schemas.admin import (
    AdminRoleUpdate,
    AdminUserImagesListResponse,
    AdminUserListResponse,
    AdminUserProfilePatch,
)
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("", response_model=AdminUserListResponse, summary="List users (paginated, optional email filter)")
def admin_list_users(
    skip: int = Query(0, ge=0, le=1_000_000),
    limit: int = Query(50, ge=1, le=500),
    email_contains: Optional[str] = Query(
        None,
        min_length=2,
        max_length=120,
        description="Case-insensitive substring match on email",
    ),
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    needle = email_contains.strip() if email_contains else None
    rows, total = admin_users_ctrl.list_users(db, skip=skip, limit=limit, email_contains=needle)
    return AdminUserListResponse(
        items=[UserResponse.model_validate(u) for u in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by id")
def admin_get_user(
    user_id: str,
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    user = admin_users_ctrl.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse, summary="Update user profile")
def admin_patch_user_profile(
    user_id: str,
    body: AdminUserProfilePatch,
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    if not admin_users_ctrl.get_user_by_id(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        user = admin_users_ctrl.get_user_by_id(db, user_id)
        return user
    user = admin_users_ctrl.patch_user_profile(db, user_id, data)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", summary="Delete user and related data")
def admin_delete_user(
    user_id: str,
    db: Database = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    if not admin_users_ctrl.delete_user(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"success": True, "message": f"User {user_id} deleted."}


@router.patch("/{user_id}/role", response_model=UserResponse, summary="Set user role (user | admin)")
def admin_set_user_role(
    user_id: str,
    body: AdminRoleUpdate,
    db: Database = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if user_id == admin.id and body.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin role",
        )
    user = admin_users_ctrl.set_user_role(db, user_id, body.role)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get(
    "/{user_id}/images",
    response_model=AdminUserImagesListResponse,
    summary="List images for a user (empty list if none)",
)
def admin_list_user_images(
    user_id: str,
    db: Database = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    if not admin_users_ctrl.get_user_by_id(db, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    images = admin_images_ctrl.list_images_for_user(db, user_id)
    return AdminUserImagesListResponse(user_id=user_id, total=len(images), images=images)
