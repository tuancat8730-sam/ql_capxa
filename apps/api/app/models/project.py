"""`organizations` (SPEC 3.3), `projects` (3.2) and `packages` (3.4, 3.6)."""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, enum_check
from app.models.user import ROLES

ORG_TYPES = (
    "investor",
    "consultant",
    "contractor",
    "supervisor",
    "auditor",
    "beneficiary",
    "bank",
    "other",
)
PACKAGE_TYPES = ("goods", "consulting")
SELECTION_FORMS = ("open_tender", "direct_appointment_short")
SELECTION_METHODS = ("one_stage_one_envelope", "one_stage_two_envelope", "short_procedure")
STAGE_CODES = (
    "S1_START",
    "S2_SELECTION",
    "S3_EXECUTION",
    "S4_ACCEPTANCE",
    "S5_PAYMENT_SETTLEMENT",
)
PACKAGE_STATUSES = (
    "planning",
    "bidding",
    "negotiating",
    "contract_signed",
    "executing",
    "accepted",
    "settled",
    "cancelled",
)
HEALTH_VALUES = ("green", "amber", "red", "grey")
CONSULTING_ROLES = ("tvqlda", "tvgs", "other")
# What a project is decides which modules it shows (see app.core.project_types).
PROJECT_TYPES = ("procurement", "software_delivery")


class Organization(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (enum_check("org_type", ORG_TYPES),)

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    representative: Mapped[str | None] = mapped_column(String(200), nullable=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    org_type: Mapped[str] = mapped_column(String(20), nullable=False)


class Project(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (enum_check("project_type", PROJECT_TYPES),)

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_type: Mapped[str] = mapped_column(
        String(30), default="procurement", server_default="procurement", nullable=False
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    investor_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    decision_maker: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_investment: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    funding_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    treasury_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    project_code_kbnn: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Package(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "packages"
    __table_args__ = (
        UniqueConstraint("project_id", "number", name="project_number"),
        CheckConstraint("number BETWEEN 1 AND 99", name="number_range"),
        enum_check("package_type", PACKAGE_TYPES),
        enum_check("selection_form", SELECTION_FORMS),
        enum_check("selection_method", SELECTION_METHODS),
        enum_check("current_stage", STAGE_CODES),
        enum_check("status", PACKAGE_STATUSES),
        enum_check("health", HEALTH_VALUES),
        enum_check("consulting_role", CONSULTING_ROLES),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_type: Mapped[str] = mapped_column(String(20), nullable=False)
    package_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    selection_form: Mapped[str | None] = mapped_column(String(30), nullable=True)
    selection_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    approved_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    etbmt_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kh_lcnt_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    winning_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    winning_org_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_stage: Mapped[str] = mapped_column(String(30), default="S1_START", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="planning", nullable=False)
    progress_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    health: Mapped[str] = mapped_column(String(10), default="grey", nullable=False)
    health_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Which consulting contract this is (project-management or supervision); drives SPEC 7.1
    # CROSS_PKG_DEPENDENCY. NULL for supply packages.
    consulting_role: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectMember(IdMixin, TimestampMixin, Base):
    """Who works on a project and in which role (the role is per project, not global)."""

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="project_user"),
        enum_check("role", tuple(sorted(ROLES))),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
