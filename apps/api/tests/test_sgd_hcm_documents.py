"""The SGD-HCM archive: folder import, folder listing, upload allowed, delete refused."""

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Project, User
from app.seed.sgd_hcm_documents import import_archive
from app.services.archive_folders import FOLDERS, folder_code_for, folder_tag
from app.services.storage import MemoryStorage
from tests.conftest import make_user
from tests.test_delivery_api import member
from tests.test_documents_api import docx_bytes, upload
from tests.test_extract import make_text_pdf
from tests.test_multi_project import H, client_as, make_project, seat

BASE = "/api/v1"
CONTRACTOR = "Nhà Thầu"
SOFTWARE = f"{CONTRACTOR}/4.Phần mềm (Yêu cầu, Đặc tả, Thiết kế, Kiểm thử, HDSD)"
BUSINESS = f"{CONTRACTOR}/3.Nghiệp vụ (Quy trình nghiệp vụ, biểu mẫu, TL khảo sát)"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def build_archive(root: Path) -> None:
    (root / SOFTWARE).mkdir(parents=True)
    (root / BUSINESS).mkdir(parents=True)
    (root / "Giám Sát").mkdir()
    spec = root / SOFTWARE / "Thuyet-minh-ky-thuat_06102026.pdf"
    spec.write_bytes(make_text_pdf("thuyet minh ky thuat cua he thong"))
    (root / BUSINESS / "Bieu-mau-gui-kem-So.docx").write_bytes(docx_bytes("Biểu mẫu gửi Sở"))
    (root / "V3 BCKTKT 06-02-26.docx").write_bytes(docx_bytes("Báo cáo kinh tế kỹ thuật"))
    # Windows leftovers that must never be uploaded.
    (root / "desktop.ini").write_text("[.ShellClassInfo]")
    (root / SOFTWARE / "desktop.ini").write_text("[.ShellClassInfo]")
    (root / "V3 BCKTKT 06-02-26.docx:Zone.Identifier").write_text("[ZoneTransfer]")
    (root / BUSINESS / "ghi-chu.txt").write_text("không được hỗ trợ")


async def admin(session: AsyncSession) -> User:
    return await make_user(session, "admin", seat=False)


# --- folder catalogue -------------------------------------------------------------------------


def test_the_folders_map_the_source_tree() -> None:
    assert folder_code_for((CONTRACTOR, SOFTWARE.split("/")[1])) == "nha-thau-4"
    assert folder_code_for((CONTRACTOR, "1.Quản lý dự án (Kế hoạch)")) == "nha-thau-1"
    assert folder_code_for(("Giám Sát",)) == "giam-sat"
    assert folder_code_for(()) == "chung"
    assert folder_code_for(("Thư mục lạ",)) == "chung"
    assert all(len(folder_tag(f.code)) <= 50 for f in FOLDERS)


# --- the import -------------------------------------------------------------------------------


async def test_import_uploads_the_real_files_with_their_folder(
    session: AsyncSession, sgd: Project, storage: MemoryStorage, tmp_path: Path
) -> None:
    build_archive(tmp_path)
    user = await admin(session)

    result = await import_archive(session, storage, tmp_path, project=sgd, uploaded_by=user.id)

    assert (result.created, result.duplicates) == (3, 0)
    assert result.junk == 3 and result.unsupported == 1
    docs = (await session.execute(select(Document).order_by(Document.title))).scalars().all()
    assert len(docs) == 3 and len(storage.objects) == 3
    spec = next(d for d in docs if d.file_name.startswith("Thuyet-minh"))
    assert spec.project_id == sgd.id and spec.package_id is None
    assert spec.tags == [folder_tag("nha-thau-4")]
    assert spec.doc_type == "software_doc" and spec.category == "execution"
    assert spec.doc_date == date(2026, 10, 6) and spec.title == "Thuyet minh ky thuat"
    assert spec.file_key in storage.objects and spec.uploaded_by == user.id
    assert spec.extraction_status == "done" and "thuyet minh" in (spec.text_content or "")
    root_file = next(d for d in docs if d.file_name.startswith("V3"))
    assert root_file.tags == [folder_tag("chung")] and root_file.doc_date is None


async def test_import_twice_adds_nothing(
    session: AsyncSession, sgd: Project, storage: MemoryStorage, tmp_path: Path
) -> None:
    build_archive(tmp_path)
    user = await admin(session)
    await import_archive(session, storage, tmp_path, project=sgd, uploaded_by=user.id)

    again = await import_archive(session, storage, tmp_path, project=sgd, uploaded_by=user.id)

    assert (again.created, again.duplicates) == (0, 3)
    assert len((await session.execute(select(Document))).scalars().all()) == 3
    assert len(storage.objects) == 3


# --- listing by folder ------------------------------------------------------------------------


async def test_folders_list_counts_and_filter_the_documents(
    storage: MemoryStorage, session: AsyncSession, sgd: Project, tmp_path: Path
) -> None:
    build_archive(tmp_path)
    c, user = await member(storage, session, sgd, "viewer")
    await import_archive(session, storage, tmp_path, project=sgd, uploaded_by=user.id)

    folders = (await c.get(f"{BASE}/document-folders")).json()

    assert [f["code"] for f in folders] == [f.code for f in FOLDERS]
    counts = {f["code"]: f["count"] for f in folders}
    assert counts["nha-thau-4"] == 1 and counts["nha-thau-3"] == 1 and counts["chung"] == 1
    assert counts["giam-sat"] == 0 and counts["nha-thau-1"] == 0
    only = (await c.get(f"{BASE}/documents", params={"folder": "nha-thau-4"})).json()
    assert [d["file_name"] for d in only["items"]] == ["Thuyet-minh-ky-thuat_06102026.pdf"]
    assert (await c.get(f"{BASE}/documents")).json()["total"] == 3


async def test_folders_are_only_for_software_delivery_projects(
    storage: MemoryStorage, session: AsyncSession
) -> None:
    procurement = await make_project(session, "MS")
    c, user = await client_as(storage, session, "p@example.test", "director")
    await seat(session, procurement, user, "director")
    c.headers[H] = str(procurement.id)

    assert (await c.get(f"{BASE}/document-folders")).status_code == 404


# --- upload yes, delete no --------------------------------------------------------------------


async def test_a_member_can_upload_into_a_folder(
    storage: MemoryStorage, session: AsyncSession, sgd: Project
) -> None:
    c, _ = await member(storage, session, sgd, "director")

    created = await upload(
        c,
        storage,
        None,
        name="bien-ban.docx",
        data=docx_bytes("biên bản"),
        mime=DOCX,
        doc_type="handover_doc",
        title="Biên bản họp",
        tags=[folder_tag("nha-thau-5")],
    )

    assert created.status_code == 201, created.text
    folders = {f["code"]: f["count"] for f in (await c.get(f"{BASE}/document-folders")).json()}
    assert folders["nha-thau-5"] == 1
    types = {t["code"]: t for t in (await c.get(f"{BASE}/doc-types")).json()}
    assert types["handover_doc"]["category"] == "acceptance"


async def test_nobody_can_delete_an_archived_document(
    storage: MemoryStorage, session: AsyncSession, sgd: Project
) -> None:
    c, _ = await member(storage, session, sgd, "admin")
    created = await upload(c, storage, None, doc_type="other", title="Hồ sơ")
    doc_id = created.json()["id"]

    resp = await c.delete(f"{BASE}/documents/{doc_id}")

    assert resp.status_code == 403
    assert (await c.get(f"{BASE}/documents/{doc_id}")).status_code == 200


async def test_a_procurement_project_can_still_delete(
    storage: MemoryStorage, session: AsyncSession
) -> None:
    procurement = await make_project(session, "MS2")
    c, user = await client_as(storage, session, "q@example.test", "admin")
    await seat(session, procurement, user, "admin")
    c.headers[H] = str(procurement.id)
    created = await upload(c, storage, None, doc_type="other", title="Hồ sơ")

    assert (await c.delete(f"{BASE}/documents/{created.json()['id']}")).status_code == 204
