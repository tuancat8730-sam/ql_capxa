"""software delivery: schedule, weekly reports, open decisions, free-text risk fields

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-08 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ALERT_TYPES = (
    "GUARANTEE_EXPIRING",
    "ADVANCE_GUARANTEE_SHORT",
    "GUARANTEE_MISSING",
    "CONTRACT_ENDING",
    "STAGE_DELAYED",
    "PROGRESS_BEHIND",
    "ISSUE_SLA",
    "DOC_MISSING",
    "DAILY_LOG_MISSING",
    "REPORT_DUE",
    "CROSS_PKG_DEPENDENCY",
    "PAYMENT_DUE",
    "PLAN_STEP_OVERDUE",
)
_NEW_ALERT_TYPES = (
    *_OLD_ALERT_TYPES,
    "TASK_LATE",
    "MILESTONE_SOON",
    "WEEKLY_REPORT_MISSING",
    "DECISION_OVERDUE",
    "RISK_VERY_HIGH",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


def _base_columns() -> list[sa.Column[object]]:
    return [
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
    ]


def upgrade() -> None:
    # --- risks: free-text fields used by software-delivery projects
    op.add_column("risks", sa.Column("group_name", sa.String(length=100), nullable=True))
    op.add_column("risks", sa.Column("owner_text", sa.String(length=200), nullable=True))
    op.add_column("risks", sa.Column("note", sa.Text(), nullable=True))

    # --- alerts: five new rule codes
    op.drop_constraint(op.f("ck_alerts_alert_type"), "alerts", type_="check")
    op.create_check_constraint(
        op.f("ck_alerts_alert_type"), "alerts", _in("alert_type", _NEW_ALERT_TYPES)
    )

    # --- the schedule
    op.create_table(
        "wbs_tasks",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("phase_code", sa.String(length=10), nullable=False),
        sa.Column("phase_name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_milestone", sa.Boolean(), nullable=False),
        sa.Column("plan_start", sa.Date(), nullable=False),
        sa.Column("plan_end", sa.Date(), nullable=False),
        sa.Column("plan_days", sa.Integer(), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("pct", sa.Integer(), nullable=False),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_end", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("pct BETWEEN 0 AND 100", name=op.f("ck_wbs_tasks_pct_range")),
        sa.CheckConstraint(
            "status IN ('not_started','in_progress','done','on_hold')",
            name=op.f("ck_wbs_tasks_status"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_wbs_tasks_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wbs_tasks")),
        sa.UniqueConstraint("project_id", "code", name="wbs_tasks_project_code"),
    )
    op.create_index("ix_wbs_tasks_project_order", "wbs_tasks", ["project_id", "sort_order"])

    # --- the contractor's weekly reports
    op.create_table(
        "weekly_reports",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("report_no", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_on", sa.Date(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("planned_pct", sa.Integer(), nullable=True),
        sa.Column("actual_pct", sa.Integer(), nullable=True),
        sa.Column("done", sa.Text(), nullable=True),
        sa.Column("issues", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.Text(), nullable=True),
        sa.Column("next_plan", sa.Text(), nullable=True),
        sa.Column(
            "risk_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        *_base_columns(),
        sa.CheckConstraint(
            "planned_pct BETWEEN 0 AND 100", name=op.f("ck_weekly_reports_planned_range")
        ),
        sa.CheckConstraint(
            "actual_pct BETWEEN 0 AND 100", name=op.f("ck_weekly_reports_actual_range")
        ),
        sa.CheckConstraint(
            "status IN ('received','needs_more')", name=op.f("ck_weekly_reports_status")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_weekly_reports_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weekly_reports")),
        sa.UniqueConstraint("project_id", "week_start", name="weekly_reports_project_week"),
    )

    # --- matters waiting for the investor
    op.create_table(
        "decision_items",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("no", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_on", sa.Date(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint(
            "status IN ('pending','decided','not_applicable')",
            name=op.f("ck_decision_items_status"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_decision_items_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_items")),
        sa.UniqueConstraint("project_id", "no", name="decision_items_project_no"),
    )


def downgrade() -> None:
    op.drop_table("decision_items")
    op.drop_table("weekly_reports")
    op.drop_index("ix_wbs_tasks_project_order", table_name="wbs_tasks")
    op.drop_table("wbs_tasks")
    # alerts raised by the new rules cannot exist under the old constraint
    op.execute(f"DELETE FROM alerts WHERE NOT ({_in('alert_type', _OLD_ALERT_TYPES)})")
    op.drop_constraint(op.f("ck_alerts_alert_type"), "alerts", type_="check")
    op.create_check_constraint(
        op.f("ck_alerts_alert_type"), "alerts", _in("alert_type", _OLD_ALERT_TYPES)
    )
    op.drop_column("risks", "note")
    op.drop_column("risks", "owner_text")
    op.drop_column("risks", "group_name")
