"""DynamoDB client singleton."""

from __future__ import annotations

import boto3
from boto3.resources.base import ServiceResource
from botocore.client import BaseClient

from app.core.config import settings

_resource: ServiceResource | None = None
_client: BaseClient | None = None


def _dynamo_kwargs() -> dict[str, str]:
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return kwargs


def get_dynamo_resource() -> ServiceResource:
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", **_dynamo_kwargs())
    return _resource


def get_dynamo_client() -> BaseClient:
    global _client
    if _client is None:
        _client = boto3.client("dynamodb", **_dynamo_kwargs())
    return _client


def table(name: str):
    return get_dynamo_resource().Table(name)
