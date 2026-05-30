from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.db.serialize import date_from_str, date_to_str, from_dynamo, from_iso, to_dynamo, to_iso, utc_now


@dataclass
class DailySteps:
    user_id: str
    step_date: date
    step_count: int = 0
    distance_km: float | None = None
    kcal_burned: int = 0
    source: str = ""
    synced_at: datetime = field(default_factory=utc_now)
    id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"{self.user_id}#{self.step_date.isoformat()}"

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "step_date": date_to_str(self.step_date),
            "step_count": self.step_count,
            "kcal_burned": self.kcal_burned,
            "source": self.source,
            "synced_at": to_iso(self.synced_at),
        }
        if self.distance_km is not None:
            item["distance_km"] = to_dynamo(self.distance_km)
        return item

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> DailySteps:
        data = from_dynamo(item)
        return cls(
            user_id=data["user_id"],
            step_date=date_from_str(data["step_date"]) or date.today(),
            step_count=int(data.get("step_count", 0)),
            distance_km=data.get("distance_km"),
            kcal_burned=int(data.get("kcal_burned", 0)),
            source=data.get("source", ""),
            synced_at=from_iso(data.get("synced_at")) or utc_now(),
            id=data.get("id") or f"{data['user_id']}#{data['step_date']}",
        )
