"""Create DynamoDB tables when SCHEMA_AUTO_CREATE is enabled."""

from __future__ import annotations

import logging

from botocore.exceptions import ClientError

from app.core.config import settings
from app.db.client import get_dynamo_client

logger = logging.getLogger(__name__)

_BILLING = {"BillingMode": "PAY_PER_REQUEST"}


def _table_defs() -> list[dict]:
    prefix = settings.dynamodb_table_prefix
    return [
        {
            "TableName": f"{prefix}-users",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "firebase_uid", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "email-index",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "firebase_uid-index",
                    "KeySchema": [{"AttributeName": "firebase_uid", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            **_BILLING,
        },
        {
            "TableName": f"{prefix}-images",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "id", "AttributeType": "S"},
                {"AttributeName": "owner_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "owner-created-index",
                    "KeySchema": [
                        {"AttributeName": "owner_id", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            **_BILLING,
        },
        {
            "TableName": f"{prefix}-user-calories",
            "KeySchema": [
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "activity_date", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "activity_date", "AttributeType": "S"},
            ],
            **_BILLING,
        },
        {
            "TableName": f"{prefix}-daily-steps",
            "KeySchema": [
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "step_date", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "step_date", "AttributeType": "S"},
            ],
            **_BILLING,
        },
        {
            "TableName": f"{prefix}-streaks",
            "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "user_id", "AttributeType": "S"}],
            **_BILLING,
        },
    ]


def ensure_tables() -> None:
    client = get_dynamo_client()
    existing = set(client.list_tables().get("TableNames", []))
    for spec in _table_defs():
        name = spec["TableName"]
        if name in existing:
            continue
        try:
            client.create_table(**spec)
            logger.info("Created DynamoDB table %s", name)
            waiter = client.get_waiter("table_exists")
            waiter.wait(TableName=name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceInUseException":
                continue
            raise
