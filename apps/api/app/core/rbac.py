"""Role x resource permission matrix (SPEC section 8)."""

from enum import Enum


class Level(Enum):
    READ = "R"
    WRITE = "W"
    APPROVE = "A"


_RANK = {Level.READ: 1, Level.WRITE: 2, Level.APPROVE: 3}
# "S" = write only on assigned packages; role-level check passes, the per-package
# check (package_access) is made in the service layer.
_GRANT_RANK = {"R": 1, "W": 2, "A": 3, "S": 2}

_ROLES = ("admin", "director", "procurement", "technical", "cost", "onsite", "clerk", "viewer")


def _row(*levels: str) -> dict[str, str]:
    return {role: lvl for role, lvl in zip(_ROLES, levels, strict=True) if lvl != "-"}


#                                  adm  dir  proc tech cost onst clrk view
MATRIX: dict[str, dict[str, str]] = {
    "project": _row("W", "R", "R", "R", "R", "-", "-", "R"),
    "package": _row("W", "W", "W", "R", "R", "R", "R", "R"),
    "contract": _row("W", "A", "W", "R", "W", "R", "R", "R"),
    "payment": _row("W", "A", "R", "R", "W", "-", "-", "R"),
    "progress": _row("W", "W", "R", "W", "R", "W", "-", "R"),
    "risk": _row("W", "A", "W", "W", "W", "W", "-", "R"),
    "document": _row("W", "W", "W", "W", "W", "W", "W", "R"),
    "sensitive_document": _row("W", "W", "S", "S", "-", "-", "-", "-"),
    "meeting": _row("W", "A", "W", "W", "R", "R", "R", "R"),
    "doc_number": _row("W", "R", "R", "R", "R", "-", "W", "R"),
    "audit_log": _row("R", "R", "-", "-", "-", "-", "-", "-"),
}


def can(role: str, resource: str, needed: Level) -> bool:
    grant = MATRIX.get(resource, {}).get(role)
    return grant is not None and _GRANT_RANK[grant] >= _RANK[needed]
