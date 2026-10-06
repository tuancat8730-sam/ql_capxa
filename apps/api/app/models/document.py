"""`documents` (SPEC 3.18), checklists (3.19) and `package_access` (section 8, sensitive docs)."""

import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, enum_check

DOC_CATEGORIES = ("legal", "selection", "contract", "execution", "acceptance", "payment", "other")
CONFIDENTIALITY = ("normal", "sensitive")
EXTRACTION_STATUSES = ("pending", "done", "needs_ocr", "unsupported", "failed")
CHECKLIST_STATUSES = ("missing", "received", "not_applicable")


class Document(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        enum_check("category", DOC_CATEGORIES),
        enum_check("confidentiality", CONFIDENTIALITY),
        enum_check("extraction_status", EXTRACTION_STATUSES),
        # Same bytes twice in one package is blocked; soft-deleted rows free the slot.
        Index(
            "uq_documents_package_sha256",
            "package_id",
            "sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND package_id IS NOT NULL"),
        ),
        Index("ix_documents_search_vector", "search_vector", postgresql_using="gin"),
        Index(
            "ix_documents_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index("ix_documents_package_current", "package_id", "is_current"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    doc_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(300), nullable=True)
    confidentiality: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    file_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_extracted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default="{}", nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChecklistTemplate(IdMixin, TimestampMixin, Base):
    __tablename__ = "checklist_templates"
    __table_args__ = (
        UniqueConstraint("package_type", "stage_code", "doc_type", "title", name="key"),
    )

    package_type: Mapped[str] = mapped_column(String(20), nullable=False)
    stage_code: Mapped[str] = mapped_column(String(30), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Days after the contract start (effective, else signed date) by which it must exist.
    due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ChecklistItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "checklist_items"
    __table_args__ = (
        UniqueConstraint("package_id", "template_id", name="package_template"),
        enum_check("status", CHECKLIST_STATUSES),
    )

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_templates.id"), nullable=True
    )
    stage_code: Mapped[str] = mapped_column(String(30), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="missing", nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PackageAccess(IdMixin, TimestampMixin, Base):
    """Who may see the sensitive documents of a package (roles marked "S" in SPEC section 8)."""

    __tablename__ = "package_access"
    __table_args__ = (UniqueConstraint("user_id", "package_id", name="user_package"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False
    )
