"""`outgoing_doc_numbers` (SPEC 3.23): outgoing document numbers, sequential per kind and year."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

DOC_KINDS = ("CV", "BC", "TB", "BB", "QD", "TT", "KH")


class OutgoingDocNumber(IdMixin, TimestampMixin, Base):
    __tablename__ = "outgoing_doc_numbers"
    __table_args__ = (
        UniqueConstraint("project_id", "year", "doc_kind", "seq", name="project_year_kind_seq"),
        enum_check("doc_kind", DOC_KINDS),
        Index("ix_outgoing_doc_numbers_year", "year"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_no: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
