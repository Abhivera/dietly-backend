from __future__ import annotations

from app.repositories.daily_steps import DailyStepsRepository
from app.repositories.images import ImageRepository
from app.repositories.streaks import StreakRepository
from app.repositories.user_calories import UserCaloriesRepository
from app.repositories.users import UserRepository


class Database:
    """Facade over DynamoDB repositories (replaces SQLAlchemy Session)."""

    def __init__(self) -> None:
        self.users = UserRepository()
        self.images = ImageRepository()
        self.user_calories = UserCaloriesRepository()
        self.daily_steps = DailyStepsRepository()
        self.streaks = StreakRepository()

    def delete_user_cascade(self, user_id: str) -> None:
        self.images.delete_all_for_user(user_id)
        self.user_calories.delete_all_for_user(user_id)
        self.daily_steps.delete_all_for_user(user_id)
        self.streaks.delete(user_id)
        self.users.delete(user_id)


_db: Database | None = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def get_db():
    yield get_database()
