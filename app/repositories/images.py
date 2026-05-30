from __future__ import annotations

from datetime import datetime, timedelta, timezone

from boto3.dynamodb.conditions import Attr, Key

from app.core.config import settings
from app.db.client import table
from app.db.serialize import to_iso, utc_now
from app.models.image import Image


class ImageRepository:
    def __init__(self) -> None:
        self._table = table(f"{settings.dynamodb_table_prefix}-images")

    def get_by_id(self, image_id: str) -> Image | None:
        resp = self._table.get_item(Key={"id": image_id})
        item = resp.get("Item")
        return Image.from_item(item) if item else None

    def get_by_id_and_owner(self, image_id: str, owner_id: str) -> Image | None:
        image = self.get_by_id(image_id)
        if image and image.owner_id == owner_id:
            return image
        return None

    def save(self, image: Image) -> Image:
        image.updated_at = utc_now()
        self._table.put_item(Item=image.to_item())
        return image

    def create(self, image: Image) -> Image:
        image.created_at = utc_now()
        self._table.put_item(Item=image.to_item())
        return image

    def delete(self, image: Image) -> None:
        self._table.delete_item(Key={"id": image.id})

    def delete_by_id(self, image_id: str) -> None:
        self._table.delete_item(Key={"id": image_id})

    def list_by_owner(
        self,
        owner_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Image]:
        kwargs: dict = {
            "IndexName": "owner-created-index",
            "KeyConditionExpression": Key("owner_id").eq(owner_id),
            "ScanIndexForward": False,
        }
        if start and end:
            kwargs["KeyConditionExpression"] = Key("owner_id").eq(owner_id) & Key("created_at").between(
                to_iso(start), to_iso(end)
            )
        elif start:
            kwargs["KeyConditionExpression"] = Key("owner_id").eq(owner_id) & Key("created_at").gte(to_iso(start))
        elif end:
            kwargs["KeyConditionExpression"] = Key("owner_id").eq(owner_id) & Key("created_at").lt(to_iso(end))

        images: list[Image] = []
        while True:
            resp = self._table.query(**kwargs)
            images.extend(Image.from_item(i) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return images

    def list_meal_dates(self, owner_id: str) -> list[datetime]:
        images = self.list_by_owner(owner_id)
        return [
            img.created_at
            for img in images
            if img.is_meal and img.created_at is not None
        ]

    def sum_meal_calories(self, owner_id: str, start: datetime, end: datetime) -> int:
        images = self.list_by_owner(owner_id, start=start, end=end)
        total = 0
        for img in images:
            if img.is_meal and img.estimated_calories:
                total += int(img.estimated_calories)
        return total

    def delete_all_for_user(self, user_id: str) -> int:
        images = self.list_by_owner(user_id)
        count = 0
        for img in images:
            self.delete(img)
            count += 1
        return count

    def count_all(self) -> int:
        total = 0
        scan_kwargs: dict = {"Select": "COUNT"}
        while True:
            resp = self._table.scan(**scan_kwargs)
            total += resp.get("Count", 0)
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return total

    @staticmethod
    def parse_date_filter(
        filter_type: str | None,
        filter_value: str | None,
    ) -> tuple[datetime | None, datetime | None]:
        if not filter_type:
            return None, None
        if not filter_value:
            raise ValueError("filter_value is required when filter_type is set")
        if filter_type == "date":
            try:
                date_obj = datetime.strptime(filter_value, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError("Invalid date filter; use YYYY-MM-DD") from e
            date_obj = date_obj.replace(tzinfo=timezone.utc)
            return date_obj, date_obj + timedelta(days=1)
        if filter_type == "week":
            import re

            match = re.match(r"(\d{4})-W(\d{2})", filter_value)
            if not match:
                raise ValueError("Invalid week filter; use YYYY-Www (ISO week)")
            try:
                year, week = int(match.group(1)), int(match.group(2))
                date_obj = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w").replace(tzinfo=timezone.utc)
                return date_obj, date_obj + timedelta(weeks=1)
            except ValueError as e:
                raise ValueError("Invalid week filter value") from e
        if filter_type == "month":
            try:
                date_obj = datetime.strptime(filter_value, "%Y-%m").replace(tzinfo=timezone.utc)
            except ValueError as e:
                raise ValueError("Invalid month filter; use YYYY-MM") from e
            if date_obj.month == 12:
                next_month = date_obj.replace(year=date_obj.year + 1, month=1)
            else:
                next_month = date_obj.replace(month=date_obj.month + 1)
            return date_obj, next_month
        raise ValueError("filter_type must be date, week, or month")
