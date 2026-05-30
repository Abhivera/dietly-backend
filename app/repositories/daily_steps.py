from __future__ import annotations

from datetime import date

from boto3.dynamodb.conditions import Key

from app.core.config import settings
from app.db.client import table
from app.db.serialize import date_to_str, utc_now
from app.models.daily_steps import DailySteps


class DailyStepsRepository:
    def __init__(self) -> None:
        self._table = table(f"{settings.dynamodb_table_prefix}-daily-steps")

    def get(self, user_id: str, step_date: date) -> DailySteps | None:
        resp = self._table.get_item(Key={"user_id": user_id, "step_date": date_to_str(step_date)})
        item = resp.get("Item")
        return DailySteps.from_item(item) if item else None

    def save(self, row: DailySteps) -> DailySteps:
        row.synced_at = utc_now()
        self._table.put_item(Item=row.to_item())
        return row

    def upsert(self, row: DailySteps) -> DailySteps:
        existing = self.get(row.user_id, row.step_date)
        if existing:
            row.synced_at = utc_now()
        self._table.put_item(Item=row.to_item())
        return row

    def list_for_user(
        self,
        user_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DailySteps]:
        kwargs: dict = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ScanIndexForward": False,
        }
        if start_date and end_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("step_date").between(
                date_to_str(start_date), date_to_str(end_date)
            )
        elif start_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("step_date").gte(
                date_to_str(start_date)
            )
        elif end_date:
            kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id) & Key("step_date").lte(
                date_to_str(end_date)
            )

        rows: list[DailySteps] = []
        while True:
            resp = self._table.query(**kwargs)
            rows.extend(DailySteps.from_item(i) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return rows[skip : skip + limit]

    def delete_all_for_user(self, user_id: str) -> int:
        rows = self.list_for_user(user_id, limit=10_000)
        for row in rows:
            self._table.delete_item(
                Key={"user_id": row.user_id, "step_date": date_to_str(row.step_date)}
            )
        return len(rows)
