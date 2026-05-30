from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.db.serialize import date_from_str, date_to_str, from_dynamo, from_iso, to_iso, utc_now


@dataclass
class UserStreak:
    user_id: str
    current_streak: int = 0
    longest_streak: int = 0
    last_logged_date: date | None = None
    updated_at: datetime = field(default_factory=utc_now)

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "user_id": self.user_id,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "updated_at": to_iso(self.updated_at),
        }
        if self.last_logged_date:
            item["last_logged_date"] = date_to_str(self.last_logged_date)
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> UserStreak:
        data = from_dynamo(item)
        return cls(
            user_id=data["user_id"],
            current_streak=int(data.get("current_streak", 0)),
            longest_streak=int(data.get("longest_streak", 0)),
            last_logged_date=date_from_str(data.get("last_logged_date")),
            updated_at=from_iso(data.get("updated_at")) or utc_now(),
        )
