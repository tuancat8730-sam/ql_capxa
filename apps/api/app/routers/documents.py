import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import ProjectDep, SessionDep, StorageDep, require, require_roles
from app.core.errors import AppError
from app.core.rbac import Level
from app.core.scope import current_project_id
from app.models import ChecklistItem, Document, Package, PackageAccess, ProjectMember, User
from app.routers.packages import package_or_404
from app.schemas.common import Page, PaginationDep
from app.schemas.document import (
    RESTRICTED_TITLE,
    AccessIn,
    AccessOut,
    DocTypeOut,
    DocumentCreate,
    DocumentDetail,
    DocumentOut,
    DocumentUpdate,
    DownloadOut,
    UploadTarget,
    UploadUrlRequest,
    UploadUrlResponse,
    VersionCreate,
    VersionOut,
)
from app.services import audit
from app.services.documents import (
    ALLOWED_MIME,
    DOC_TYPE_CODES,
    DOC_TYPES,
    INLINE_MIME,
    accessible_package_ids,
    build_key,
    can_view,
    can_write,
    process_document,
    refresh_search_vector,
    visible_clause,
)

router = APIRouter(tags=["documents"])

Reader = Annotated[User, Depends(require("document", Level.READ))]
Writer = Annotated[User, Depends(require("document", Level.WRITE))]
Governor = Annotated[User, Depends(require_roles("admin", "director"))]

_META_FIELDS = (
    "doc_type",
    "title",
    "category",
    "doc_no",
    "doc_date",
    "issuer",
    "confidentiality",
    "contract_id",
    "tags",
    "notes",
)


def _forbidden() -> AppError:
    return AppError(403, "forbidden", "Bạn không có quyền với tài liệu này")


def _restricted(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        package_id=doc.package_id,
        restricted=True,
        title=RESTRICTED_TITLE,
        confidentiality="sensitive",
    )


async def _load(session: AsyncSession, document_id: uuid.UUID) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None or doc.deleted_at is not None or doc.project_id != current_project_id():
        raise AppError(404, "not_found", "Không tìm thấy tài liệu")
    return doc


async def _load_visible(session: AsyncSession, user: User, document_id: uuid.UUID) -> Document:
    doc = await _load(session, document_id)
    if not can_view(user, doc, await accessible_package_ids(session, user)):
        raise _forbidden()
    return doc


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/doc-types", response_model=list[DocTypeOut])
async def list_doc_types(_: Reader) -> list[DocTypeOut]:
    return [DocTypeOut(code=d.code, label=d.label, category=d.category) for d in DOC_TYPES]


# --- listing and search -----------------------------------------------------------------------


@router.get("/documents", response_model=Page[DocumentOut])
async def list_documents(
    user: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    package_id: uuid.UUID | None = None,
    contract_id: uuid.UUID | None = None,
    category: str | None = None,
    doc_type: str | None = None,
    confidentiality: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    current_only: bool = True,
) -> Page[DocumentOut]:
    """Without `q` hidden files appear as redacted stubs; with `q` they are excluded entirely."""
    access_ids = await accessible_package_ids(session, user)
    stmt = select(Document).where(
        Document.deleted_at.is_(None), Document.project_id == current_project_id()
    )
    if current_only:
        stmt = stmt.where(Document.is_current.is_(True))
    for column, value in (
        (Document.package_id, package_id),
        (Document.contract_id, contract_id),
        (Document.category, category),
        (Document.doc_type, doc_type),
        (Document.confidentiality, confidentiality),
    ):
        if value is not None:
            stmt = stmt.where(column == value)

    query = (q or "").strip()
    if query:
        unaccent = func.unaccent
        needle = f"%{_escape_like(query)}%"
        vector_query = func.plainto_tsquery("simple", unaccent(query))
        stmt = stmt.where(visible_clause(user, access_ids)).where(
            or_(
                unaccent(Document.title).ilike(unaccent(needle), escape="\\"),
                unaccent(func.coalesce(Document.doc_no, "")).ilike(unaccent(needle), escape="\\"),
                unaccent(func.coalesce(Document.notes, "")).ilike(unaccent(needle), escape="\\"),
                unaccent(Document.file_name).ilike(unaccent(needle), escape="\\"),
                Document.search_vector.op("@@")(vector_query),
            )
        )
        order = (
            func.ts_rank(Document.search_vector, vector_query).desc(),
            Document.created_at.desc(),
        )
    else:
        order = (Document.doc_date.desc().nulls_last(), Document.created_at.desc())

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(*order, Document.id)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    items = [
        DocumentOut.model_validate(d) if can_view(user, d, access_ids) else _restricted(d)
        for d in rows
    ]
    return Page[DocumentOut](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def read_document(
    document_id: uuid.UUID, user: Reader, session: SessionDep
) -> DocumentDetail:
    doc = await _load_visible(session, user, document_id)
    chain = await _version_chain(session, doc)
    detail = DocumentDetail.model_validate(doc)
    detail.versions = [VersionOut.model_validate(v) for v in chain]
    return detail


async def _version_chain(session: AsyncSession, doc: Document) -> list[Document]:
    """Every version of the same logical document, newest first."""
    root = doc
    while root.parent_document_id is not None:
        parent = await session.get(Document, root.parent_document_id)
        if parent is None:
            break
        root = parent
    chain = [root]
    cursor = root
    while True:
        child = (
            (
                await session.execute(
                    select(Document).where(
                        Document.parent_document_id == cursor.id, Document.deleted_at.is_(None)
                    )
                )
            )
            .scalars()
            .first()
        )
        if child is None:
            break
        chain.append(child)
        cursor = child
    return sorted(chain, key=lambda d: d.version, reverse=True)


# --- upload flow (SPEC section 9) ---------------------------------------------------------------


def _check_file(mime_type: str, size_bytes: int) -> None:
    if mime_type not in ALLOWED_MIME:
        raise AppError(422, "validation_error", "Định dạng tệp không được phép", ["mime_type"])
    limit = get_settings().max_upload_bytes
    if size_bytes > limit:
        raise AppError(
            422, "validation_error", f"Tệp vượt quá {limit // (1024 * 1024)} MB", ["size_bytes"]
        )


async def _package_scope(
    session: AsyncSession, user: User, package_id: uuid.UUID | None, confidentiality: str
) -> Package | None:
    package = await package_or_404(session, package_id) if package_id else None
    effective = "sensitive" if package and package.is_sensitive else confidentiality
    access_ids = await accessible_package_ids(session, user)
    if not can_write(user, effective, package_id, access_ids):
        raise _forbidden()
    return package


@router.post("/documents/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    body: UploadUrlRequest,
    user: Writer,
    session: SessionDep,
    storage: StorageDep,
    project: ProjectDep,
) -> UploadUrlResponse:
    _check_file(body.mime_type, body.size_bytes)
    parent: Document | None = None
    package_id = body.package_id
    version = 1
    if body.parent_document_id:
        parent = await _load_visible(session, user, body.parent_document_id)
        if not parent.is_current:
            raise AppError(409, "conflict", "Chỉ tạo phiên bản mới từ bản hiện hành")
        package_id, version = parent.package_id, parent.version + 1
    package = await _package_scope(
        session, user, package_id, parent.confidentiality if parent else "normal"
    )
    if package is not None and package.project_id != project.id:
        raise AppError(422, "validation_error", "Gói thầu không thuộc dự án", ["package_id"])

    settings = get_settings()
    document_id = uuid.uuid4()
    key = build_key(project.id, package_id, document_id, version, body.file_name)
    presigned = await storage.presign_upload(key, body.mime_type, settings.upload_url_ttl_seconds)
    return UploadUrlResponse(
        document_id=document_id,
        file_key=key,
        version=version,
        upload=UploadTarget(url=presigned.url, method=presigned.method, headers=presigned.headers),
        expires_in=settings.upload_url_ttl_seconds,
        max_bytes=settings.max_upload_bytes,
    )


async def _verified_upload(
    session: AsyncSession,
    storage: StorageDep,
    *,
    project_id: uuid.UUID,
    package_id: uuid.UUID | None,
    version: int,
    ref: Any,
) -> str:
    """Check the object really exists with the declared size; return its server-side sha256."""
    _check_file(ref.mime_type, ref.size_bytes)
    expected = build_key(project_id, package_id, ref.document_id, version, ref.file_name)
    if ref.file_key != expected:
        raise AppError(
            422, "validation_error", "Khóa tệp không khớp với yêu cầu tải lên", ["file_key"]
        )
    info = await storage.head(ref.file_key)
    if info is None:
        raise AppError(422, "validation_error", "Tệp chưa được tải lên", ["file_key"])
    if info.size != ref.size_bytes:
        raise AppError(422, "validation_error", "Kích thước tệp không khớp", ["size_bytes"])
    digest = hashlib.sha256()
    async for chunk in storage.read_chunks(ref.file_key):
        digest.update(chunk)
    sha = digest.hexdigest()
    if ref.sha256 and ref.sha256.lower() != sha:
        raise AppError(422, "validation_error", "Mã băm SHA-256 không khớp", ["sha256"])
    return sha


async def _reject_duplicate(
    session: AsyncSession, package_id: uuid.UUID | None, sha256: str
) -> None:
    if package_id is None:
        return
    existing = (
        (
            await session.execute(
                select(Document).where(
                    Document.package_id == package_id,
                    Document.sha256 == sha256,
                    Document.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        raise AppError(
            409,
            "duplicate_document",
            "Tệp trùng nội dung đã có trong gói này",
            {"document_id": str(existing.id), "title": existing.title},
        )


async def _link_checklist(session: AsyncSession, doc: Document, parent: Document | None) -> None:
    if parent is not None:
        await session.execute(
            update(ChecklistItem)
            .where(ChecklistItem.document_id == parent.id)
            .values(document_id=doc.id)
        )
        return
    if doc.package_id is None:
        return
    item = (
        (
            await session.execute(
                select(ChecklistItem)
                .where(
                    ChecklistItem.package_id == doc.package_id,
                    ChecklistItem.doc_type == doc.doc_type,
                    ChecklistItem.status == "missing",
                )
                .order_by(ChecklistItem.sort_order)
            )
        )
        .scalars()
        .first()
    )
    if item is not None:
        item.status, item.document_id = "received", doc.id


async def _persist(
    session: AsyncSession, doc: Document, user: User, request: Request, parent: Document | None
) -> None:
    session.add(doc)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "duplicate_document", "Tệp trùng nội dung đã có trong gói này") from exc
    if parent is not None:
        parent.is_current = False
    await _link_checklist(session, doc, parent)
    await refresh_search_vector(session, doc.id)
    audit.record(
        session,
        action="create",
        entity_type="document",
        entity_id=doc.id,
        user_id=user.id,
        changes={
            "title": doc.title,
            "doc_type": doc.doc_type,
            "version": doc.version,
            "package_id": doc.package_id,
            "confidentiality": doc.confidentiality,
            "size_bytes": doc.size_bytes,
            "sha256": doc.sha256,
        },
        request=request,
    )
    await session.commit()
    await session.refresh(doc)


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentCreate,
    request: Request,
    background: BackgroundTasks,
    user: Writer,
    session: SessionDep,
    storage: StorageDep,
    project: ProjectDep,
) -> Document:
    package = await _package_scope(session, user, body.package_id, body.confidentiality)
    if package is not None and package.project_id != project.id:
        raise AppError(422, "validation_error", "Gói thầu không thuộc dự án", ["package_id"])
    if body.doc_type not in DOC_TYPE_CODES:
        raise AppError(422, "validation_error", "Loại tài liệu không hợp lệ", ["doc_type"])

    sha = await _verified_upload(
        session, storage, project_id=project.id, package_id=body.package_id, version=1, ref=body
    )
    await _reject_duplicate(session, body.package_id, sha)

    confidentiality = "sensitive" if package and package.is_sensitive else body.confidentiality
    doc = Document(
        id=body.document_id,
        project_id=project.id,
        package_id=body.package_id,
        contract_id=body.contract_id,
        category=body.category or DOC_TYPE_CODES[body.doc_type].category,
        doc_type=body.doc_type,
        title=body.title,
        doc_no=body.doc_no,
        doc_date=body.doc_date,
        issuer=body.issuer,
        confidentiality=confidentiality,
        file_key=body.file_key,
        file_name=body.file_name,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        sha256=sha,
        version=1,
        is_current=True,
        tags=body.tags,
        notes=body.notes,
        uploaded_by=user.id,
        created_by=user.id,
        updated_by=user.id,
    )
    await _persist(session, doc, user, request, None)
    background.add_task(process_document, doc.id, storage)
    return doc


@router.post("/documents/{document_id}/versions", response_model=DocumentOut, status_code=201)
async def create_version(
    document_id: uuid.UUID,
    body: VersionCreate,
    request: Request,
    background: BackgroundTasks,
    user: Writer,
    session: SessionDep,
    storage: StorageDep,
) -> Document:
    parent = await _load_visible(session, user, document_id)
    if not parent.is_current:
        raise AppError(409, "conflict", "Chỉ tạo phiên bản mới từ bản hiện hành")
    await _package_scope(session, user, parent.package_id, parent.confidentiality)
    if parent.confidentiality == "sensitive":
        access_ids = await accessible_package_ids(session, user)
        if not can_write(user, "sensitive", parent.package_id, access_ids):
            raise _forbidden()

    sha = await _verified_upload(
        session,
        storage,
        project_id=parent.project_id,
        package_id=parent.package_id,
        version=parent.version + 1,
        ref=body,
    )
    await _reject_duplicate(session, parent.package_id, sha)

    doc = Document(
        id=body.document_id,
        project_id=parent.project_id,
        package_id=parent.package_id,
        contract_id=parent.contract_id,
        category=parent.category,
        doc_type=parent.doc_type,
        title=body.title or parent.title,
        doc_no=body.doc_no if body.doc_no is not None else parent.doc_no,
        doc_date=body.doc_date or parent.doc_date,
        issuer=parent.issuer,
        confidentiality=parent.confidentiality,
        file_key=body.file_key,
        file_name=body.file_name,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        sha256=sha,
        version=parent.version + 1,
        parent_document_id=parent.id,
        is_current=True,
        tags=list(parent.tags),
        notes=body.notes if body.notes is not None else parent.notes,
        uploaded_by=user.id,
        created_by=user.id,
        updated_by=user.id,
    )
    await _persist(session, doc, user, request, parent)
    background.add_task(process_document, doc.id, storage)
    return doc


# --- download, edit, delete ---------------------------------------------------------------------


@router.get("/documents/{document_id}/download-url", response_model=DownloadOut)
async def download_url(
    document_id: uuid.UUID,
    request: Request,
    user: Reader,
    session: SessionDep,
    storage: StorageDep,
    inline: bool = False,
) -> DownloadOut:
    doc = await _load_visible(session, user, document_id)
    as_inline = inline and doc.mime_type in INLINE_MIME
    ttl = get_settings().download_url_ttl_seconds
    url = await storage.presign_download(
        doc.file_key, doc.file_name, doc.mime_type, ttl, inline=as_inline
    )
    audit.record(
        session,
        action="download",
        entity_type="document",
        entity_id=doc.id,
        user_id=user.id,
        changes={
            "file_name": doc.file_name,
            "version": doc.version,
            "confidentiality": doc.confidentiality,
        },
        request=request,
    )
    await session.commit()
    return DownloadOut(
        url=url, expires_in=ttl, file_name=doc.file_name, mime_type=doc.mime_type, inline=as_inline
    )


@router.patch("/documents/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> Document:
    doc = await _load_visible(session, user, document_id)
    access_ids = await accessible_package_ids(session, user)
    if not can_write(user, doc.confidentiality, doc.package_id, access_ids):
        raise _forbidden()
    changes = body.model_dump(exclude_unset=True)
    nulls = [
        k
        for k in ("doc_type", "title", "category", "confidentiality")
        if k in changes and changes[k] is None
    ]
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    if "doc_type" in changes:
        if changes["doc_type"] not in DOC_TYPE_CODES:
            raise AppError(422, "validation_error", "Loại tài liệu không hợp lệ", ["doc_type"])
        changes.setdefault("category", DOC_TYPE_CODES[changes["doc_type"]].category)
    if "confidentiality" in changes and changes["confidentiality"] != doc.confidentiality:
        package = await session.get(Package, doc.package_id) if doc.package_id else None
        if user.effective_role not in {"admin", "director"}:
            raise _forbidden()
        if changes["confidentiality"] == "normal" and package and package.is_sensitive:
            raise AppError(409, "conflict", "Gói nhạy cảm: tài liệu phải ở mức nhạy cảm")
    if "tags" in changes and changes["tags"] is None:
        changes["tags"] = []

    before = audit.snapshot(doc, changes)
    for field, value in changes.items():
        setattr(doc, field, value)
    doc.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(doc, changes))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="document",
            entity_id=doc.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.flush()
    await refresh_search_vector(session, doc.id)
    await session.commit()
    await session.refresh(doc)
    return doc


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    doc = await _load_visible(session, user, document_id)
    access_ids = await accessible_package_ids(session, user)
    if not can_write(user, doc.confidentiality, doc.package_id, access_ids):
        raise _forbidden()
    doc.deleted_at = datetime.now(UTC)
    doc.is_current = False
    doc.updated_by = user.id
    # Deleting the latest version makes the previous one current again.
    if doc.parent_document_id is not None:
        parent = await session.get(Document, doc.parent_document_id)
        if parent is not None and parent.deleted_at is None:
            parent.is_current = True
    await session.execute(
        update(ChecklistItem)
        .where(ChecklistItem.document_id == doc.id)
        .values(
            document_id=doc.parent_document_id if doc.parent_document_id else None,
            status="received" if doc.parent_document_id else "missing",
        )
    )
    audit.record(
        session,
        action="delete",
        entity_type="document",
        entity_id=doc.id,
        user_id=user.id,
        changes={"title": doc.title, "version": doc.version},
        request=request,
    )
    await session.commit()
    return Response(status_code=204)


# --- sensitive-document access (package_access) -------------------------------------------------


async def _access_users(session: AsyncSession, package_id: uuid.UUID) -> list[User]:
    return list(
        (
            await session.execute(
                select(User)
                .join(PackageAccess, PackageAccess.user_id == User.id)
                .where(PackageAccess.package_id == package_id)
                .order_by(User.full_name)
            )
        )
        .scalars()
        .all()
    )


@router.get("/packages/{package_id}/access", response_model=AccessOut)
async def read_access(package_id: uuid.UUID, _: Governor, session: SessionDep) -> AccessOut:
    await package_or_404(session, package_id)
    return AccessOut.model_validate({"users": await _access_users(session, package_id)})


@router.put("/packages/{package_id}/access", response_model=AccessOut)
async def replace_access(
    package_id: uuid.UUID,
    body: AccessIn,
    request: Request,
    admin: Governor,
    session: SessionDep,
) -> AccessOut:
    await package_or_404(session, package_id)
    wanted = set(body.user_ids)
    if wanted:
        found = (
            (
                await session.execute(
                    select(User).where(User.id.in_(wanted), User.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
        roles = dict(
            (
                await session.execute(
                    select(ProjectMember.user_id, ProjectMember.role).where(
                        ProjectMember.project_id == current_project_id(),
                        ProjectMember.user_id.in_(wanted),
                    )
                )
            ).all()
        )
        bad = [str(u.id) for u in found if roles.get(u.id) not in {"procurement", "technical"}]
        missing = [str(i) for i in wanted - {u.id for u in found}]
        if bad or missing:
            raise AppError(
                422,
                "validation_error",
                "Chỉ gán được người dùng đang hoạt động có vai trò đấu thầu hoặc kỹ thuật",
                bad + missing,
            )
    current = {u.id for u in await _access_users(session, package_id)}
    for user_id in wanted - current:
        session.add(PackageAccess(user_id=user_id, package_id=package_id, created_by=admin.id))
    if current - wanted:
        rows = (
            (
                await session.execute(
                    select(PackageAccess).where(
                        PackageAccess.package_id == package_id,
                        PackageAccess.user_id.in_(current - wanted),
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            await session.delete(row)
    audit.record(
        session,
        action="update",
        entity_type="package_access",
        entity_id=package_id,
        user_id=admin.id,
        changes={
            "granted": sorted(str(i) for i in wanted - current),
            "revoked": sorted(str(i) for i in current - wanted),
        },
        request=request,
    )
    await session.commit()
    return AccessOut.model_validate({"users": await _access_users(session, package_id)})
