"""Audit trail writer (SPEC 4.18). Callers commit; audit rows ride the caller's transaction."""

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog

_SECRET_KEYS = ("password", "token", "secret", "hash")


def json_safe(value: Any) -> Any:
    """Make a column value storable in the JSONB `changes` column."""
    if isinstance(value, Decimal):
        return format(value, "f")  # plain digits, never 5.15E+10
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe(v) for v in value]
    return value


def scrub(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop any key that could carry a credential before it is persisted."""
    if data is None:
        return None
    return {
        k: json_safe(v) for k, v in data.items() if not any(s in k.lower() for s in _SECRET_KEYS)
    }


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        k: {"before": json_safe(before.get(k)), "after": json_safe(v)}
        for k, v in after.items()
        if before.get(k) != v
    }


def snapshot(obj: object, fields: Iterable[str]) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields}


def record(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None,
    user_id: uuid.UUID | None,
    changes: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes=scrub(changes),
        ip=request.client.host if request and request.client else None,
        user_agent=(request.headers.get("user-agent", "")[:500] or None) if request else None,
    )
    session.add(row)
    return row
