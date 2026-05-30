from __future__ import annotations

from datetime import date

from boto3.dynamodb.conditions import Key

from app.core.config import settings
from app.db.client import table
from app.db.serialize import date_to_str, utc_now
from app.models.user_calories import UserCalories


class UserCaloriesRepository:
    def __init__(self) -> None:
        self._table = table(f"{settings.dynamodb_table_prefix}-user-calories")

    def get(self, user_id: str, activity_date: date) -> UserCalories | None:
        resp = self._table.get_item(
            Key={"user_id": user_id, "activity_date": date_to_str(activity_date)}
        )
        item = resp.get("Item")
        return UserCalories.from_item(item) if item else None

    def get_by_id(self, calories_id: str, user_id: str) -> UserCalories | None:
        parts = calories_id.rsplit("#", 1)
        if len(parts) != 2:
            return None
        uid, date_str = parts
        if uid != user_id:
            return None
        from app.db.serialize import date_from_str

        activity_date = date_from_str(date_str)
        if not activity_date:
            return None
        return self.get(user_id, activity_date)

    def save(self, row: UserCalories) -> UserCalories:
        row.updated_at = utc_now()
        self._table.put_item(Item=row.to_item())
        return row

    def create(self, row: UserCalories) -> UserCalories:
        row.created_at = utc_now()
        self._table.put_item(Item=row.to_item())
        return row

    def delete(self, row: UserCalories) -> None:
        self._table.delete_item(
            Key={"user_id": row.user_id, "activity_date": date_to_str(row.activity_date)}
        )

    def list_for_user(
        self,
        user_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[UserCalories]:
        kwargs: dict = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ScanIndexForward": False,
        }
        if start_date and end_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("activity_date").between(
                date_to_str(start_date), date_to_str(end_date)
            )
        elif start_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("activity_date").gte(
                date_to_str(start_date)
            )
        elif end_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("activity_date").lte(
                date_to_str(end_date)
            )

        rows: list[UserCalories] = []
        while True:
            resp = self._table.query(**kwargs)
            rows.extend(UserCalories.from_item(i) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return rows[skip : skip + limit]

    def delete_all_for_user(self, user_id: str) -> int:
        rows = self.list_for_user(user_id, limit=10_000)
        for row in rows:
            self.delete(row)
        return len(rows)
