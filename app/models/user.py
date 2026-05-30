from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from app.db.serialize import date_from_str, date_to_str, from_dynamo, from_iso, to_dynamo, to_iso, utc_now


@dataclass
class User:
    id: str
    email: str
    firebase_uid: str | None = None
    password_hash: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    role: str = "user"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None
    gender: str | None = None
    age: int | None = None
    weight: int | None = None
    height: int | None = None
    goal_weight: int | None = None
    step_goal: int = 8000

    @classmethod
    def new(cls, **kwargs: Any) -> User:
        return cls(id=str(uuid4()), **kwargs)

    def to_item(self) -> dict[str, Any]:
        item = {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "step_goal": self.step_goal,
            "created_at": to_iso(self.created_at),
        }
        optional = {
            "firebase_uid": self.firebase_uid,
            "password_hash": self.password_hash,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "updated_at": to_iso(self.updated_at),
            "gender": self.gender,
            "age": self.age,
            "weight": self.weight,
            "height": self.height,
            "goal_weight": self.goal_weight,
        }
        for key, value in optional.items():
            if value is not None:
                item[key] = value
        return to_dynamo(item)

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> User:
        data = from_dynamo(item)
        return cls(
            id=data["id"],
            email=data["email"],
            firebase_uid=data.get("firebase_uid"),
            password_hash=data.get("password_hash"),
            full_name=data.get("full_name"),
            avatar_url=data.get("avatar_url"),
            role=data.get("role", "user"),
            created_at=from_iso(data["created_at"]) or utc_now(),
            updated_at=from_iso(data.get("updated_at")),
            gender=data.get("gender"),
            age=data.get("age"),
            weight=data.get("weight"),
            height=data.get("height"),
            goal_weight=data.get("goal_weight"),
            step_goal=int(data.get("step_goal", 8000)),
        )
