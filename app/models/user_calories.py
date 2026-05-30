from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.db.serialize import date_from_str, date_to_str, from_dynamo, from_iso, to_dynamo, to_iso, utc_now


def total_burned_from_json(calories_burned: list | None) -> int:
    if not calories_burned:
        return 0
    total = 0
    for activity in calories_burned:
        try:
            total += int(activity.get("calories", 0))
        except (ValueError, TypeError):
            continue
    return total


@dataclass
class UserCalories:
    user_id: str
    activity_date: date
    calories_burned: list
    total_burned: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None
    id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.user_id}#{self.activity_date.isoformat()}"

    def to_item(self) -> dict[str, Any]:
        item = {
            "id": self.id,
            "user_id": self.user_id,
            "activity_date": date_to_str(self.activity_date),
            "calories_burned": to_dynamo(self.calories_burned),
            "total_burned": self.total_burned,
            "created_at": to_iso(self.created_at),
        }
        if self.updated_at:
            item["updated_at"] = to_iso(self.updated_at)
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> UserCalories:
        data = from_dynamo(item)
        return cls(
            user_id=data["user_id"],
            activity_date=date_from_str(data["activity_date"]) or date.today(),
            calories_burned=data.get("calories_burned") or [],
            total_burned=int(data.get("total_burned", 0)),
            created_at=from_iso(data.get("created_at")) or utc_now(),
            updated_at=from_iso(data.get("updated_at")),
            id=data.get("id") or f"{data['user_id']}#{data['activity_date']}",
        )
