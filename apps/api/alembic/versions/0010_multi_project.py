"""multi project: project type, members, project_id on every project-level table

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-08 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES = "'admin','director','procurement','technical','cost','onsite','clerk','viewer'"
# Every row that exists today belongs to the one project there is (the commune-level project).
_FIRST_PROJECT = "(SELECT id FROM projects ORDER BY created_at LIMIT 1)"


def _add_project_id(
    table: str,
    *,
    backfill: str,
    nullable: bool,
    fk: bool = True,
    index: str | None = None,
) -> None:
    """Add `project_id`, fill it for existing rows, then tighten it.

    `index` is only for tables with no unique constraint that already leads with project_id.
    """
    op.add_column(table, sa.Column("project_id", sa.UUID(), nullable=True))
    op.execute(f"UPDATE {table} SET project_id = {backfill} WHERE project_id IS NULL")  # noqa: S608
    if not nullable:
        op.alter_column(table, "project_id", nullable=False)
    if fk:
        op.create_foreign_key(
            op.f(f"fk_{table}_project_id_projects"), table, "projects", ["project_id"], ["id"]
        )
    if index:
        op.create_index(index, table, ["project_id"])


def upgrade() -> None:
    # --- projects: type, short name, archive flag
    op.add_column("projects", sa.Column("short_name", sa.String(length=100), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "project_type", sa.String(length=30), server_default="procurement", nullable=False
        ),
    )
    op.add_column(
        "projects",
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_projects_project_type"),
        "projects",
        "project_type IN ('procurement','software_delivery')",
    )

    # --- members: a role per project
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
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
        sa.CheckConstraint(f"role IN ({_ROLES})", name=op.f("ck_project_members_role")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_members_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_project_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.UniqueConstraint("project_id", "user_id", name="project_user"),
    )
    # Everyone who has an account today works on the existing project with their account role;
    # system administrators need no seat.
    op.execute(
        """
        INSERT INTO project_members (id, project_id, user_id, role)
        SELECT gen_random_uuid(), p.id, u.id, u.role
        FROM projects p CROSS JOIN users u
        WHERE u.role <> 'admin' AND p.deleted_at IS NULL
        """
    )

    # --- project_id on the tables that only reached the project through a package
    from_package = "SELECT project_id FROM packages WHERE id = {t}.package_id"
    _add_project_id(
        "issues",
        backfill=f"COALESCE(({from_package.format(t='issues')}), {_FIRST_PROJECT})",
        nullable=False,
    )
    _add_project_id(
        "change_requests",
        backfill=f"COALESCE(({from_package.format(t='change_requests')}), {_FIRST_PROJECT})",
        nullable=False,
    )
    _add_project_id(
        "alerts",
        backfill=f"COALESCE(({from_package.format(t='alerts')}), {_FIRST_PROJECT})",
        nullable=False,
        index="ix_alerts_project",
    )
    _add_project_id("outgoing_doc_numbers", backfill=_FIRST_PROJECT, nullable=False)
    # audit rows about accounts and logins belong to no project
    _add_project_id(
        "audit_log", backfill="NULL", nullable=True, fk=False, index="ix_audit_log_project"
    )
    op.execute(
        f"UPDATE audit_log SET project_id = {_FIRST_PROJECT} "  # noqa: S608
        "WHERE action <> 'login' AND entity_type NOT IN ('user')"
    )

    # --- codes and numbers are unique inside a project, not across the system
    op.drop_constraint(op.f("uq_risks_code"), "risks", type_="unique")
    op.create_unique_constraint("risks_project_code", "risks", ["project_id", "code"])
    op.drop_constraint(op.f("uq_issues_code"), "issues", type_="unique")
    op.create_unique_constraint("issues_project_code", "issues", ["project_id", "code"])
    op.drop_constraint(op.f("uq_change_requests_code"), "change_requests", type_="unique")
    op.create_unique_constraint(
        "change_requests_project_code", "change_requests", ["project_id", "code"]
    )
    op.drop_constraint("year_kind_seq", "outgoing_doc_numbers", type_="unique")
    op.create_unique_constraint(
        "project_year_kind_seq",
        "outgoing_doc_numbers",
        ["project_id", "year", "doc_kind", "seq"],
    )


def downgrade() -> None:
    op.drop_constraint("project_year_kind_seq", "outgoing_doc_numbers", type_="unique")
    op.create_unique_constraint(
        "year_kind_seq", "outgoing_doc_numbers", ["year", "doc_kind", "seq"]
    )
    op.drop_constraint("change_requests_project_code", "change_requests", type_="unique")
    op.create_unique_constraint(op.f("uq_change_requests_code"), "change_requests", ["code"])
    op.drop_constraint("issues_project_code", "issues", type_="unique")
    op.create_unique_constraint(op.f("uq_issues_code"), "issues", ["code"])
    op.drop_constraint("risks_project_code", "risks", type_="unique")
    op.create_unique_constraint(op.f("uq_risks_code"), "risks", ["code"])

    op.drop_index("ix_audit_log_project", table_name="audit_log")
    op.drop_index("ix_alerts_project", table_name="alerts")
    for table in ("outgoing_doc_numbers", "alerts", "change_requests", "issues"):
        op.drop_constraint(op.f(f"fk_{table}_project_id_projects"), table, type_="foreignkey")
    for table in ("audit_log", "outgoing_doc_numbers", "alerts", "change_requests", "issues"):
        op.drop_column(table, "project_id")

    op.drop_table("project_members")
    op.drop_constraint(op.f("ck_projects_project_type"), "projects", type_="check")
    op.drop_column("projects", "is_archived")
    op.drop_column("projects", "project_type")
    op.drop_column("projects", "short_name")
