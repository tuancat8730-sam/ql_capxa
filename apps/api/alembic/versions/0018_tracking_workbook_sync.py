"""tracking workbook sync: CBDT package numbers, workbook risk source, task source keys

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_RISK_SOURCES = ("de_cuong", "analysis", "manual")
_NEW_RISK_SOURCES = (*_OLD_RISK_SOURCES, "workbook")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


def upgrade() -> None:
    # Preparation (CBDT) packages are stored as numbers 101..103 so they sit beside 1..8.
    op.drop_constraint(op.f("ck_packages_number_range"), "packages", type_="check")
    op.create_check_constraint(
        op.f("ck_packages_number_range"), "packages", "number BETWEEN 1 AND 999"
    )

    op.drop_constraint(op.f("ck_risks_source"), "risks", type_="check")
    op.create_check_constraint(op.f("ck_risks_source"), "risks", _in("source", _NEW_RISK_SOURCES))

    # Stable key of a milestone row in the workbook, so a weekly import updates instead of duplicating.
    op.add_column("tasks", sa.Column("source_key", sa.String(length=40), nullable=True))
    op.create_index(
        "ix_tasks_package_source_key",
        "tasks",
        ["package_id", "source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_package_source_key", table_name="tasks")
    op.drop_column("tasks", "source_key")

    # Rows written by the workbook sync cannot exist under the old constraint.
    op.execute("DELETE FROM risks WHERE source = 'workbook'")
    op.drop_constraint(op.f("ck_risks_source"), "risks", type_="check")
    op.create_check_constraint(op.f("ck_risks_source"), "risks", _in("source", _OLD_RISK_SOURCES))

    op.execute("DELETE FROM packages WHERE number > 99")
    op.drop_constraint(op.f("ck_packages_number_range"), "packages", type_="check")
    op.create_check_constraint(
        op.f("ck_packages_number_range"), "packages", "number BETWEEN 1 AND 99"
    )
