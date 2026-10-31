"""Shared types for the tracking sync: one row of the report and the field-writing helper."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Change:
    entity: str
    key: str
    action: str  # create | update | unchanged | missing_in_workbook
    fields: tuple[str, ...] = ()


def set_fields(obj: Any, values: dict[str, Any]) -> tuple[str, ...]:
    """Write non-empty values onto an ORM object; return the names that actually changed."""
    changed: list[str] = []
    for name, value in values.items():
        if value is None:
            continue
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            changed.append(name)
    return tuple(changed)
