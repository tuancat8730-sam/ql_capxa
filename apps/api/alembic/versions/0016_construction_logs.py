"""construction logs: the contractor's weekly site diary of a software-delivery project

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-17 14:00:00.000000

One log per project and reporting week, with day-by-day entries, a carry-over table and the
work of a consortium member. Lines point at a WBS task by its code (no foreign key: the code is
only unique inside a project).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _log_fk() -> sa.Column[object]:
    return sa.Column("log_id", sa.UUID(), nullable=False)


def _personnel() -> sa.Column[object]:
    return sa.Column(
        "personnel", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
    )


def _log_fk_constraint(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["log_id"],
        ["construction_logs.id"],
        name=op.f(f"fk_{table}_log_id_construction_logs"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "construction_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("recipients", sa.Text(), nullable=True),
        sa.Column("reporter_org", sa.String(length=200), nullable=True),
        sa.Column("contract_ref", sa.Text(), nullable=True),
        sa.Column("coordinator", sa.String(length=200), nullable=True),
        sa.Column("environment_note", sa.Text(), nullable=True),
        sa.Column("overall_status", sa.Text(), nullable=True),
        sa.Column("key_results", sa.Text(), nullable=True),
        sa.Column("issues", sa.Text(), nullable=True),
        sa.Column("coordination_requests", sa.Text(), nullable=True),
        sa.Column("related_report", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_construction_logs_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_logs")),
        sa.UniqueConstraint("project_id", "week_start", name="construction_logs_week"),
    )

    op.create_table(
        "construction_log_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        _log_fk(),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("phase_code", sa.String(length=10), nullable=False),
        sa.Column("task_code", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        _personnel(),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=True),
        sa.Column("delay_days", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "state IN ('not_started','in_progress','done','blocked')",
            name=op.f("ck_construction_log_entries_state"),
        ),
        sa.CheckConstraint(
            "delay_days >= 0", name=op.f("ck_construction_log_entries_delay_days_range")
        ),
        _log_fk_constraint("construction_log_entries"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_log_entries")),
    )
    op.create_index(
        "ix_construction_log_entries_order",
        "construction_log_entries",
        ["log_id", "entry_date", "seq"],
    )
    op.create_index("ix_construction_log_entries_task", "construction_log_entries", ["task_code"])

    op.create_table(
        "construction_log_carryovers",
        sa.Column("id", sa.UUID(), nullable=False),
        _log_fk(),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("phase_code", sa.String(length=10), nullable=False),
        sa.Column("task_code", sa.String(length=20), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("result_to_date", sa.Text(), nullable=True),
        sa.Column("next_week", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        _log_fk_constraint("construction_log_carryovers"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_log_carryovers")),
    )
    op.create_index(
        "ix_construction_log_carryovers_order", "construction_log_carryovers", ["log_id", "seq"]
    )

    op.create_table(
        "construction_log_member_work",
        sa.Column("id", sa.UUID(), nullable=False),
        _log_fk(),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("member_name", sa.String(length=200), nullable=False),
        sa.Column("item", sa.Text(), nullable=False),
        sa.Column("plan_ref", sa.Text(), nullable=True),
        _personnel(),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column("issues_actions", sa.Text(), nullable=True),
        _log_fk_constraint("construction_log_member_work"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_log_member_work")),
    )
    op.create_index(
        "ix_construction_log_member_work_order", "construction_log_member_work", ["log_id", "seq"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_log_member_work_order", table_name="construction_log_member_work"
    )
    op.drop_table("construction_log_member_work")
    op.drop_index("ix_construction_log_carryovers_order", table_name="construction_log_carryovers")
    op.drop_table("construction_log_carryovers")
    op.drop_index("ix_construction_log_entries_task", table_name="construction_log_entries")
    op.drop_index("ix_construction_log_entries_order", table_name="construction_log_entries")
    op.drop_table("construction_log_entries")
    op.drop_table("construction_logs")
