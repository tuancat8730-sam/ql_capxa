"""Document domain logic: types, keys, visibility of sensitive files, search index, checklists."""

import asyncio
import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import ColumnElement, and_, false, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.rbac import Level, can, needs_assignment
from app.models import (
    ChecklistItem,
    ChecklistTemplate,
    Contract,
    Document,
    Package,
    PackageAccess,
    User,
)
from app.services.extract import extract_text
from app.services.storage import Storage

log = logging.getLogger(__name__)

MAX_EXTRACT_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class DocType:
    code: str
    label: str
    category: str


# SPEC 4.6 standard `doc_type` codes, each with its default category group.
DOC_TYPES: tuple[DocType, ...] = (
    DocType("decision_invest", "Quyết định đầu tư", "legal"),
    DocType("decision_estimate", "Quyết định phê duyệt dự toán", "legal"),
    DocType("decision_kh_lcnt", "Quyết định phê duyệt KHLCNT", "legal"),
    DocType("etbmt", "E-TBMT", "selection"),
    DocType("etbmt_approval", "Quyết định phê duyệt E-HSMT", "selection"),
    DocType("bid_opening_minutes", "Biên bản mở thầu", "selection"),
    DocType("evaluation_report", "Báo cáo đánh giá E-HSDT", "selection"),
    DocType("appraisal_report", "Báo cáo thẩm định KQLCNT", "selection"),
    DocType("decision_selection_result", "Quyết định phê duyệt KQLCNT", "selection"),
    DocType("acceptance_letter", "Thư chấp thuận E-HSDT và trao hợp đồng", "selection"),
    DocType("contract", "Hợp đồng", "contract"),
    DocType("contract_completion_minutes", "Biên bản hoàn thiện hợp đồng", "contract"),
    DocType("guarantee_performance", "Bảo đảm thực hiện hợp đồng", "contract"),
    DocType("guarantee_advance", "Bảo lãnh tạm ứng", "contract"),
    DocType("guarantee_warranty", "Bảo lãnh bảo hành", "contract"),
    DocType("delivery_plan", "Kế hoạch giao hàng chi tiết", "execution"),
    DocType("delivery_notice", "Thông báo lịch giao hàng", "execution"),
    DocType("coc_cq", "CO, CQ", "execution"),
    DocType("calibration_cert", "Chứng nhận kiểm định, hiệu chuẩn", "execution"),
    DocType("site_inspection_minutes", "Biên bản kiểm tra hiện trường (QL-08)", "execution"),
    DocType("acceptance_minutes", "Biên bản nghiệm thu (QL-09)", "acceptance"),
    DocType("handover_minutes", "Biên bản bàn giao (QL-10)", "acceptance"),
    DocType("supervisor_report", "Báo cáo kết quả giám sát", "acceptance"),
    DocType("value_statement", "Bảng xác định giá trị khối lượng (QL-11)", "payment"),
    DocType("invoice", "Hóa đơn", "payment"),
    DocType("liquidation_minutes", "Biên bản thanh lý (QL-15)", "payment"),
    DocType("settlement_checklist", "Danh mục hồ sơ quyết toán (QL-16)", "payment"),
    DocType("meeting_minutes", "Biên bản họp (QL-04)", "execution"),
    DocType("proposal_letter", "Tờ trình, đề xuất (QL-05)", "execution"),
    DocType("report_weekly", "Báo cáo tuần", "execution"),
    DocType("report_monthly", "Báo cáo tháng", "execution"),
    DocType("report_final", "Báo cáo kết thúc", "execution"),
    DocType("report_adhoc", "Báo cáo đột xuất", "execution"),
    DocType("photo", "Ảnh hiện trường", "execution"),
    DocType("other", "Khác", "other"),
)
DOC_TYPE_CODES = {d.code: d for d in DOC_TYPES}

# SPEC section 9: pdf, docx, xlsx, doc, xls, jpg, png, zip.
ALLOWED_MIME = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.ms-excel",
        "image/jpeg",
        "image/png",
        "application/zip",
        "application/x-zip-compressed",
    }
)
INLINE_MIME = frozenset({"application/pdf", "image/jpeg", "image/png"})


def safe_filename(name: str) -> str:
    """ASCII-only key segment: no diacritics, no spaces, extension preserved (SPEC section 9)."""
    base = name.replace("đ", "d").replace("Đ", "D")
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    stem, dot, ext = base.rpartition(".")
    if not dot or not re.fullmatch(r"[a-z0-9]{1,10}", ext):
        stem, ext = base, ""
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-_")[:100].strip("-_") or "file"
    return f"{stem}.{ext}" if ext else stem


def build_key(
    project_id: uuid.UUID,
    package_id: uuid.UUID | None,
    doc_id: uuid.UUID,
    version: int,
    file_name: str,
) -> str:
    scope = str(package_id) if package_id else "project"
    return f"projects/{project_id}/packages/{scope}/{doc_id}/v{version}/{safe_filename(file_name)}"


# --- who may see / write sensitive documents (SPEC section 8) ---------------------------------


async def accessible_package_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    rows = await session.execute(
        select(PackageAccess.package_id).where(PackageAccess.user_id == user.id)
    )
    return set(rows.scalars().all())


def can_view(user: User, doc: Document, access_ids: set[uuid.UUID]) -> bool:
    if doc.confidentiality == "normal":
        return can(user.role, "document", Level.READ)
    return can_touch_sensitive(user, doc.package_id, access_ids, Level.READ)


def can_touch_sensitive(
    user: User, package_id: uuid.UUID | None, access_ids: set[uuid.UUID], level: Level
) -> bool:
    if not can(user.role, "sensitive_document", level):
        return False
    if needs_assignment(user.role, "sensitive_document"):
        return package_id is not None and package_id in access_ids
    return True


def can_write(
    user: User, confidentiality: str, package_id: uuid.UUID | None, access_ids: set[uuid.UUID]
) -> bool:
    if confidentiality == "sensitive":
        return can_touch_sensitive(user, package_id, access_ids, Level.WRITE)
    return can(user.role, "document", Level.WRITE)


def visible_clause(user: User, access_ids: set[uuid.UUID]) -> ColumnElement[bool]:
    """SQL twin of `can_view`: used for search so hidden files never leak through matches."""
    normal = (
        Document.confidentiality == "normal" if can(user.role, "document", Level.READ) else false()
    )
    if not can(user.role, "sensitive_document", Level.READ):
        return normal
    sensitive = Document.confidentiality == "sensitive"
    if needs_assignment(user.role, "sensitive_document"):
        sensitive = and_(sensitive, Document.package_id.in_(access_ids or {uuid.UUID(int=0)}))
    return or_(normal, sensitive)


# --- search index -----------------------------------------------------------------------------


async def refresh_search_vector(session: AsyncSession, document_id: uuid.UUID) -> None:
    """Diacritic-free full-text vector over everything a person might type (SPEC 4.6)."""
    await session.execute(
        text(
            """
            UPDATE documents SET search_vector = to_tsvector(
                'simple',
                unaccent(concat_ws(' ', title, doc_no, issuer, notes, file_name,
                                   array_to_string(tags, ' '), text_content))
            )
            WHERE id = :id
            """
        ),
        {"id": document_id},
    )


async def process_document(document_id: uuid.UUID, storage: Storage) -> None:
    """Background job: read the uploaded file, extract its text, refresh the search vector."""
    async with get_sessionmaker()() as session:
        doc = await session.get(Document, document_id)
        if doc is None or doc.deleted_at is not None:
            return
        status, content = "failed", None
        try:
            if doc.size_bytes > MAX_EXTRACT_BYTES:
                status = "unsupported"
            else:
                data = await storage.read_bytes(doc.file_key, MAX_EXTRACT_BYTES)
                result = await asyncio.to_thread(extract_text, data, doc.mime_type, doc.file_name)
                status, content = result.status, result.text
        except Exception:  # noqa: BLE001  (never lose an upload because indexing failed)
            log.exception("text extraction failed for document %s", document_id)
        doc.text_content = content
        doc.text_extracted = status == "done"
        doc.extraction_status = status
        await session.flush()
        await refresh_search_vector(session, doc.id)
        await session.commit()


# --- checklists -------------------------------------------------------------------------------


async def contract_start(session: AsyncSession, package_id: uuid.UUID) -> object | None:
    contract = (
        (
            await session.execute(
                select(Contract)
                .where(Contract.package_id == package_id, Contract.deleted_at.is_(None))
                .order_by(Contract.signed_date.nulls_last())
            )
        )
        .scalars()
        .first()
    )
    return (contract.effective_date or contract.signed_date) if contract else None


async def instantiate_checklist(session: AsyncSession, package: Package) -> int:
    """Create the missing checklist rows for a package from the templates; idempotent."""
    start = await contract_start(session, package.id)
    templates = (
        (
            await session.execute(
                select(ChecklistTemplate)
                .where(ChecklistTemplate.package_type == package.package_type)
                .order_by(ChecklistTemplate.sort_order)
            )
        )
        .scalars()
        .all()
    )
    existing = set(
        (
            await session.execute(
                select(ChecklistItem.template_id).where(ChecklistItem.package_id == package.id)
            )
        )
        .scalars()
        .all()
    )
    created = 0
    for tpl in templates:
        if tpl.id in existing:
            continue
        due = None
        if start is not None and tpl.due_offset_days is not None:
            due = start + timedelta(days=tpl.due_offset_days)  # type: ignore[operator]
        session.add(
            ChecklistItem(
                package_id=package.id,
                template_id=tpl.id,
                stage_code=tpl.stage_code,
                doc_type=tpl.doc_type,
                title=tpl.title,
                required=tpl.required,
                status="missing",
                due_date=due,
                sort_order=tpl.sort_order,
            )
        )
        created += 1
    await session.flush()
    await link_existing_documents(session, package.id)
    return created


async def link_existing_documents(session: AsyncSession, package_id: uuid.UUID) -> None:
    """Attach already-uploaded current documents to still-missing items of the same type."""
    missing = (
        (
            await session.execute(
                select(ChecklistItem)
                .where(ChecklistItem.package_id == package_id, ChecklistItem.status == "missing")
                .order_by(ChecklistItem.sort_order)
            )
        )
        .scalars()
        .all()
    )
    taken = set(
        (
            await session.execute(
                select(ChecklistItem.document_id).where(
                    ChecklistItem.package_id == package_id, ChecklistItem.document_id.is_not(None)
                )
            )
        )
        .scalars()
        .all()
    )
    for item in missing:
        doc = (
            (
                await session.execute(
                    select(Document)
                    .where(
                        Document.package_id == package_id,
                        Document.doc_type == item.doc_type,
                        Document.is_current.is_(True),
                        Document.deleted_at.is_(None),
                        Document.id.not_in(taken or {uuid.UUID(int=0)}),
                    )
                    .order_by(Document.created_at)
                )
            )
            .scalars()
            .first()
        )
        if doc is not None:
            item.status, item.document_id = "received", doc.id
            taken.add(doc.id)
