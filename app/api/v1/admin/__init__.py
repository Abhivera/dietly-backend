from fastapi import APIRouter

from app.api.v1.admin import images as admin_images
from app.api.v1.admin import stats as admin_stats
from app.api.v1.admin import users as admin_users

router = APIRouter()
router.include_router(admin_stats.router, prefix="/stats")
router.include_router(admin_users.router, prefix="/users")
router.include_router(admin_images.router, prefix="/images")
