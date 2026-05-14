from fastapi import APIRouter

from app.api.v1 import daily_steps, images, meal, public_food_analysis, steps, user_calories, users
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(meal.router, prefix="/meal", tags=["meal"])
api_router.include_router(
    public_food_analysis.router,
    prefix="/public",
    tags=["public-food-analysis"],
)
api_router.include_router(user_calories.router, prefix="/user-calories", tags=["user-calories"])
api_router.include_router(daily_steps.router, prefix="/daily-steps", tags=["daily-steps"])
api_router.include_router(steps.router, prefix="/steps", tags=["steps"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
