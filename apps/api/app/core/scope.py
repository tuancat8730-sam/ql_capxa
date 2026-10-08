"""The project of the request being served, for code that cannot take it as a parameter.

`project_context` (core/deps.py) sets it once per request; helpers that fetch an entity by id use
it to refuse entities of another project, and the audit log uses it to tag its rows.
"""

import uuid
from contextvars import ContextVar
from typing import Any

from sqlalchemy import select
from sqlalchemy.sql import Select

from app.core.errors import AppError
from app.models import Package

_project_id: ContextVar[uuid.UUID | None] = ContextVar("project_id", default=None)


def set_project_id(project_id: uuid.UUID | None) -> None:
    _project_id.set(project_id)


def current_project_id_or_none() -> uuid.UUID | None:
    return _project_id.get()


def current_project_id() -> uuid.UUID:
    pid = _project_id.get()
    if pid is None:  # a route that reads project data forgot the project dependency
        raise RuntimeError("no project in scope for this request")
    return pid


def package_ids() -> Select[Any]:
    """Ids of the live packages of the current project, for `Entity.package_id.in_(...)`."""
    return select(Package.id).where(
        Package.project_id == current_project_id(), Package.deleted_at.is_(None)
    )


def not_found_unless_in_project(entity_project_id: uuid.UUID | None, what: str) -> None:
    if entity_project_id != current_project_id():
        raise AppError(404, "not_found", what)


def contract_ids() -> Select[Any]:
    """Ids of the live contracts of the current project's packages."""
    from app.models import Contract

    return select(Contract.id).where(
        Contract.package_id.in_(package_ids()), Contract.deleted_at.is_(None)
    )
