from __future__ import annotations

from app.core.config import settings
from app.db.client import table
from app.db.serialize import utc_now
from app.models.streaks import UserStreak


class StreakRepository:
    def __init__(self) -> None:
        self._table = table(f"{settings.dynamodb_table_prefix}-streaks")

    def get(self, user_id: str) -> UserStreak | None:
        resp = self._table.get_item(Key={"user_id": user_id})
        item = resp.get("Item")
        return UserStreak.from_item(item) if item else None

    def save(self, row: UserStreak) -> UserStreak:
        row.updated_at = utc_now()
        self._table.put_item(Item=row.to_item())
        return row

    def delete(self, user_id: str) -> None:
        self._table.delete_item(Key={"user_id": user_id})
