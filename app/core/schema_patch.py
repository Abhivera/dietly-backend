"""Idempotent Postgres patch so `users.password_hash` exists and is NOT NULL."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def apply_postgres_users_jwt_schema(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return

    insp = inspect(engine)
    if not insp.has_table("users"):
        return

    stmts = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "UPDATE users SET password_hash = '' WHERE password_hash IS NULL",
        "ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL",
    ]

    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))

    logger.info("postgres_schema_patch: users.password_hash ensured")
