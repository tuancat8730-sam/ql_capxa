"""SPEC section 8 permission matrix, encoded verbatim as the expected truth table."""

import pytest

from app.core.rbac import Level, can

# resource -> role -> level ("-" none, R, W, A, "S" = only assigned packages)
MATRIX: dict[str, dict[str, str]] = {
    "project": dict(
        admin="W",
        director="R",
        procurement="R",
        technical="R",
        cost="R",
        onsite="-",
        clerk="-",
        viewer="R",
    ),
    "package": dict(
        admin="W",
        director="W",
        procurement="W",
        technical="R",
        cost="R",
        onsite="R",
        clerk="R",
        viewer="R",
    ),
    "contract": dict(
        admin="W",
        director="A",
        procurement="W",
        technical="R",
        cost="W",
        onsite="R",
        clerk="R",
        viewer="R",
    ),
    "payment": dict(
        admin="W",
        director="A",
        procurement="R",
        technical="R",
        cost="W",
        onsite="-",
        clerk="-",
        viewer="R",
    ),
    "progress": dict(
        admin="W",
        director="W",
        procurement="R",
        technical="W",
        cost="R",
        onsite="W",
        clerk="-",
        viewer="R",
    ),
    "risk": dict(
        admin="W",
        director="A",
        procurement="W",
        technical="W",
        cost="W",
        onsite="W",
        clerk="-",
        viewer="R",
    ),
    "document": dict(
        admin="W",
        director="W",
        procurement="W",
        technical="W",
        cost="W",
        onsite="W",
        clerk="W",
        viewer="R",
    ),
    "sensitive_document": dict(
        admin="W",
        director="W",
        procurement="S",
        technical="S",
        cost="-",
        onsite="-",
        clerk="-",
        viewer="-",
    ),
    "meeting": dict(
        admin="W",
        director="A",
        procurement="W",
        technical="W",
        cost="R",
        onsite="R",
        clerk="R",
        viewer="R",
    ),
    "doc_number": dict(
        admin="W",
        director="R",
        procurement="R",
        technical="R",
        cost="R",
        onsite="-",
        clerk="W",
        viewer="R",
    ),
    "audit_log": dict(
        admin="R",
        director="R",
        procurement="-",
        technical="-",
        cost="-",
        onsite="-",
        clerk="-",
        viewer="-",
    ),
}

_ORDER = {"-": 0, "R": 1, "W": 2, "A": 3}


def _cases():
    for resource, roles in MATRIX.items():
        for role, lvl in roles.items():
            for needed in (Level.READ, Level.WRITE, Level.APPROVE):
                yield resource, role, lvl, needed


@pytest.mark.parametrize(("resource", "role", "lvl", "needed"), list(_cases()))
def test_matrix(resource: str, role: str, lvl: str, needed: Level) -> None:
    if lvl == "S":
        # Role-level check passes; the per-package check is enforced in the service layer.
        assert can(role, resource, Level.READ)
        assert can(role, resource, Level.WRITE)
        return
    expected = _ORDER[lvl] >= {"R": 1, "W": 2, "A": 3}[needed.value]
    assert can(role, resource, needed) is expected


def test_unknown_role_or_resource_denied() -> None:
    assert not can("ghost", "project", Level.READ)
    assert not can("admin", "nonexistent", Level.READ)
