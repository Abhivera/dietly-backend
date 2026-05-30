from __future__ import annotations

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.core.config import settings
from app.db.client import table
from app.db.serialize import utc_now
from app.models.user import User


class UserRepository:
    def __init__(self) -> None:
        self._table = table(f"{settings.dynamodb_table_prefix}-users")

    def get_by_id(self, user_id: str) -> User | None:
        resp = self._table.get_item(Key={"id": user_id})
        item = resp.get("Item")
        return User.from_item(item) if item else None

    def get_by_firebase_uid(self, firebase_uid: str) -> User | None:
        resp = self._table.query(
            IndexName="firebase_uid-index",
            KeyConditionExpression=Key("firebase_uid").eq(firebase_uid),
            Limit=1,
        )
        items = resp.get("Items", [])
        return User.from_item(items[0]) if items else None

    def get_by_email(self, email: str) -> User | None:
        resp = self._table.query(
            IndexName="email-index",
            KeyConditionExpression=Key("email").eq(email.lower().strip()),
            Limit=1,
        )
        items = resp.get("Items", [])
        return User.from_item(items[0]) if items else None

    def get_by_firebase_uid_or_email(self, firebase_uid: str, email: str) -> User | None:
        user = self.get_by_firebase_uid(firebase_uid)
        if user:
            return user
        return self.get_by_email(email)

    def save(self, user: User) -> User:
        user.updated_at = utc_now()
        self._table.put_item(Item=user.to_item())
        return user

    def create(self, user: User) -> User:
        user.created_at = utc_now()
        try:
            self._table.put_item(
                Item=user.to_item(),
                ConditionExpression=Attr("id").not_exists(),
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError("User already exists") from exc
            raise
        return user

    def delete(self, user_id: str) -> bool:
        user = self.get_by_id(user_id)
        if not user:
            return False
        self._table.delete_item(Key={"id": user_id})
        return True

    def list_all(self, skip: int = 0, limit: int = 100, email_contains: str | None = None) -> tuple[list[User], int]:
        users: list[User] = []
        scan_kwargs: dict = {}
        if email_contains:
            scan_kwargs["FilterExpression"] = Attr("email").contains(email_contains.lower())
        while True:
            resp = self._table.scan(**scan_kwargs)
            users.extend(User.from_item(i) for i in resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        users.sort(key=lambda u: u.created_at)
        total = len(users)
        return users[skip : skip + limit], total

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

    def count_by_role(self, role: str) -> int:
        total = 0
        scan_kwargs: dict = {
            "Select": "COUNT",
            "FilterExpression": Attr("role").eq(role),
        }
        while True:
            resp = self._table.scan(**scan_kwargs)
            total += resp.get("Count", 0)
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return total

    def update_fields(self, user: User, fields: dict) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        return self.save(user)
