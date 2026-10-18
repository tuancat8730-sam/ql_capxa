"""Import the SGD-HCM archive ("Tài Liệu Lưu trữ") into the documents of the SGD-HCM project.

    python -m app.seed.sgd_hcm_documents [DIR]        (DIR defaults to $SGD_HCM_ARCHIVE_DIR)

Each file goes to object storage and becomes a project-level `documents` row (SPEC 3.18) tagged
with its folder. Safe to run again: a file whose bytes the project already holds is skipped.
Windows leftovers (`desktop.ini`, `*:Zone.Identifier`, `Thumbs.db`) and types the system does
not accept are skipped and counted.
"""

import asyncio
import hashlib
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.scope import set_project_id
from app.models import Document, Project, User
from app.seed.sgd_hcm_progress import PROJECT_CODE
from app.services import audit
from app.services.archive_folders import FOLDER_BY_CODE, folder_code_for, folder_tag
from app.services.documents import (
    DOC_TYPE_CODES,
    build_key,
    process_document,
    refresh_search_vector,
)
from app.services.storage import Storage, build_storage

MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".doc": "application/msword",
    ".xls": "application/vnd.ms-excel",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".zip": "application/zip",
}
JUNK_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
_DATE_SUFFIX = re.compile(r"_(\d{2})(\d{2})(\d{4})$")


@dataclass
class ImportResult:
    created: int = 0
    duplicates: int = 0
    junk: int = 0
    unsupported: int = 0


def is_junk(name: str) -> bool:
    lowered = name.casefold()
    return lowered in JUNK_NAMES or lowered.endswith(":zone.identifier") or lowered.startswith("~$")


def title_and_date(stem: str) -> tuple[str, date | None]:
    """`Thuyet-minh-ky-thuat_06102026` -> ("Thuyet minh ky thuat", 2026-10-06)."""
    doc_date = None
    match = _DATE_SUFFIX.search(stem)
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            doc_date = date(year, month, day)
            stem = stem[: match.start()]
        except ValueError:
            doc_date = None
    title = re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", stem)).strip()
    return title or stem, doc_date


async def import_archive(
    session: AsyncSession,
    storage: Storage,
    root: Path,
    *,
    project: Project,
    uploaded_by: uuid.UUID,
) -> ImportResult:
    result = ImportResult()
    set_project_id(project.id)
    known = set(
        (
            await session.execute(
                select(Document.sha256).where(
                    Document.project_id == project.id, Document.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    limit = get_settings().max_upload_bytes
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if is_junk(path.name):
            result.junk += 1
            continue
        mime = MIME_BY_SUFFIX.get(path.suffix.casefold())
        if mime is None or path.stat().st_size > limit or path.stat().st_size == 0:
            result.unsupported += 1
            continue
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha in known:
            result.duplicates += 1
            continue

        folder = FOLDER_BY_CODE[folder_code_for(path.relative_to(root).parent.parts)]
        title, doc_date = title_and_date(path.stem)
        doc_id = uuid.uuid4()
        key = build_key(project.id, None, doc_id, 1, path.name)
        await storage.put_bytes(key, data, mime)
        doc = Document(
            id=doc_id,
            project_id=project.id,
            category=DOC_TYPE_CODES[folder.doc_type].category,
            doc_type=folder.doc_type,
            title=title,
            doc_date=doc_date,
            file_key=key,
            file_name=path.name,
            mime_type=mime,
            size_bytes=len(data),
            sha256=sha,
            version=1,
            is_current=True,
            tags=[folder_tag(folder.code)],
            uploaded_by=uploaded_by,
            created_by=uploaded_by,
            updated_by=uploaded_by,
        )
        session.add(doc)
        await session.flush()
        await refresh_search_vector(session, doc.id)
        audit.record(
            session,
            action="create",
            entity_type="document",
            entity_id=doc.id,
            user_id=uploaded_by,
            changes={"title": title, "folder": folder.code, "source": "archive_import"},
        )
        await session.commit()
        await process_document(doc.id, storage)
        await session.refresh(doc)
        known.add(sha)
        result.created += 1
    set_project_id(None)
    return result


async def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SGD_HCM_ARCHIVE_DIR", ""))
    if not root.is_dir():
        raise SystemExit(f"Archive folder not found: {root!s} (pass it or set SGD_HCM_ARCHIVE_DIR)")
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@qlda.local").strip().lower()
    storage = build_storage(get_settings())
    await storage.ensure_bucket()
    async with get_sessionmaker()() as session:
        project = (
            await session.execute(select(Project).where(Project.code == PROJECT_CODE))
        ).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if project is None or user is None:
            raise SystemExit("Run `python -m app.seed.run` first: project or admin is missing")
        result = await import_archive(session, storage, root, project=project, uploaded_by=user.id)
    print(
        f"Imported {result.created} file(s); skipped {result.duplicates} already present, "
        f"{result.junk} system file(s), {result.unsupported} unsupported/empty"
    )
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
