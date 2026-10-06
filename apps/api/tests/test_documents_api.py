"""M4: documents — upload flow, versions, diacritic-free search, sensitive-file visibility."""

import hashlib
import io
import uuid

import httpx
import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Document, Package, PackageAccess, User
from app.seed.project import seed_project
from app.services.documents import safe_filename
from app.services.storage import MemoryStorage
from tests.conftest import ALL_ROLES, make_user
from tests.test_extract import make_text_pdf

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALL_DOC_WRITERS = {"admin", "director", "procurement", "technical", "cost", "onsite", "clerk"}


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


async def upload(
    c: httpx.AsyncClient,
    storage: MemoryStorage,
    package: Package | None,
    *,
    name: str = "bao-lanh.pdf",
    data: bytes | None = None,
    mime: str = PDF,
    doc_type: str = "guarantee_advance",
    title: str = "Bảo lãnh tạm ứng",
    **extra: object,
) -> httpx.Response:
    data = data if data is not None else make_text_pdf(f"noi dung {uuid.uuid4()}")
    pid = str(package.id) if package else None
    req = await c.post(
        "/api/v1/documents/upload-url",
        json={"file_name": name, "mime_type": mime, "size_bytes": len(data), "package_id": pid},
    )
    assert req.status_code == 200, req.text
    info = req.json()
    storage.put(info["file_key"], data)
    return await c.post(
        "/api/v1/documents",
        json={
            "document_id": info["document_id"],
            "file_key": info["file_key"],
            "file_name": name,
            "mime_type": mime,
            "size_bytes": len(data),
            "doc_type": doc_type,
            "title": title,
            "package_id": pid,
            **extra,
        },
    )


def docx_bytes(*paragraphs: str) -> bytes:
    doc = DocxDocument()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- upload flow ------------------------------------------------------------------------------


async def test_upload_url_shape_and_confirm(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    pkg = seeded[4]
    data = make_text_pdf("Bao lanh tam ung so 123 cua ngan hang")
    req = (
        await c.post(
            "/api/v1/documents/upload-url",
            json={
                "file_name": "Bảo lãnh tạm ứng số 1.pdf",
                "mime_type": PDF,
                "size_bytes": len(data),
                "package_id": str(pkg.id),
            },
        )
    ).json()
    assert req["file_key"].endswith(f"/{req['document_id']}/v1/bao-lanh-tam-ung-so-1.pdf")
    assert f"/packages/{pkg.id}/" in req["file_key"]
    assert (req["expires_in"], req["max_bytes"], req["version"]) == (600, 100 * 1024 * 1024, 1)
    assert req["upload"]["method"] == "PUT" and req["upload"]["headers"]["Content-Type"] == PDF

    storage.put(req["file_key"], data)
    resp = await c.post(
        "/api/v1/documents",
        json={
            "document_id": req["document_id"],
            "file_key": req["file_key"],
            "file_name": "Bảo lãnh tạm ứng số 1.pdf",
            "mime_type": PDF,
            "size_bytes": len(data),
            "doc_type": "guarantee_advance",
            "title": "Bảo lãnh tạm ứng",
            "doc_no": "BL-001",
            "doc_date": "2026-09-15",
            "package_id": str(pkg.id),
            "tags": ["tpbank"],
        },
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["sha256"] == hashlib.sha256(data).hexdigest()  # computed by the server
    assert (doc["category"], doc["version"], doc["is_current"]) == ("contract", 1, True)
    assert doc["uploaded_by"] is not None and doc["tags"] == ["tpbank"]
    assert "file_key" not in doc
    # the text layer was indexed by the background job
    full = (await c.get(f"/api/v1/documents/{doc['id']}")).json()
    assert full["extraction_status"] == "done"


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda b: {**b, "mime_type": "application/x-msdownload"}, "mime_type"),
        (lambda b: {**b, "size_bytes": 101 * 1024 * 1024}, "size_bytes"),
    ],
)
async def test_upload_url_rejects_bad_type_and_oversize(
    mutate, field: str, session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    body = {"file_name": "a.pdf", "mime_type": PDF, "size_bytes": 10}
    resp = await c.post("/api/v1/documents/upload-url", json=mutate(body))
    assert resp.status_code == 422 and field in resp.json()["error"]["details"]


async def test_upload_url_validation_and_unknown_package(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    assert (await c.post("/api/v1/documents/upload-url", json={})).status_code == 422
    zero = {"file_name": "a.pdf", "mime_type": PDF, "size_bytes": 0}
    assert (await c.post("/api/v1/documents/upload-url", json=zero)).status_code == 422
    ghost = {
        "file_name": "a.pdf",
        "mime_type": PDF,
        "size_bytes": 5,
        "package_id": str(uuid.uuid4()),
    }
    # the single project must exist first
    assert (await c.post("/api/v1/documents/upload-url", json=ghost)).status_code == 404


async def test_confirm_rejects_missing_object_size_key_and_checksum(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    pkg = seeded[4]
    data = make_text_pdf("ban ghi hop dong so 71 gia tri lon")
    req = (
        await c.post(
            "/api/v1/documents/upload-url",
            json={
                "file_name": "a.pdf",
                "mime_type": PDF,
                "size_bytes": len(data),
                "package_id": str(pkg.id),
            },
        )
    ).json()
    base = {
        "document_id": req["document_id"],
        "file_key": req["file_key"],
        "file_name": "a.pdf",
        "mime_type": PDF,
        "size_bytes": len(data),
        "doc_type": "contract",
        "title": "Hợp đồng",
        "package_id": str(pkg.id),
    }
    post = lambda body: c.post("/api/v1/documents", json=body)  # noqa: E731
    assert (await post(base)).status_code == 422  # nothing uploaded yet
    storage.put(req["file_key"], data)
    assert (await post({**base, "size_bytes": len(data) + 1})).status_code == 422
    assert (await post({**base, "file_key": req["file_key"] + "x"})).status_code == 422
    assert (await post({**base, "sha256": "0" * 64})).status_code == 422
    assert (await post({**base, "sha256": "zz"})).status_code == 422
    assert (await post({**base, "doc_type": "nonsense"})).status_code == 422
    assert (await post({**base, "title": ""})).status_code == 422
    assert (await post({**base, "mime_type": "text/html"})).status_code == 422
    ok = await post({**base, "sha256": hashlib.sha256(data).hexdigest().upper()})
    assert ok.status_code == 201


async def test_key_cannot_be_borrowed_from_another_document(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    first = (await upload(c, storage, seeded[4])).json()
    victim_key = (
        await session.execute(select(Document.file_key).where(Document.id == first["id"]))
    ).scalar_one()
    data = make_text_pdf("another")
    req = (
        await c.post(
            "/api/v1/documents/upload-url",
            json={
                "file_name": "a.pdf",
                "mime_type": PDF,
                "size_bytes": len(data),
                "package_id": str(seeded[4].id),
            },
        )
    ).json()
    resp = await c.post(
        "/api/v1/documents",
        json={
            "document_id": req["document_id"],
            "file_key": victim_key,
            "file_name": "a.pdf",
            "mime_type": PDF,
            "size_bytes": len(data),
            "doc_type": "other",
            "title": "x",
            "package_id": str(seeded[4].id),
        },
    )
    assert resp.status_code == 422


async def test_duplicate_content_is_blocked_within_a_package_only(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    data = make_text_pdf("trung noi dung hop dong")
    first = await upload(c, storage, seeded[4], data=data)
    assert first.status_code == 201
    dup = await upload(c, storage, seeded[4], data=data, title="Bản sao")
    assert dup.status_code == 409
    err = dup.json()["error"]
    assert (
        err["code"] == "duplicate_document" and err["details"]["document_id"] == first.json()["id"]
    )
    assert (await upload(c, storage, seeded[6], data=data)).status_code == 201  # other package ok
    assert (
        await upload(c, storage, None, data=data)
    ).status_code == 201  # project level never blocks
    assert (await upload(c, storage, None, data=data)).status_code == 201


async def test_deleting_frees_the_checksum_slot(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    data = make_text_pdf("xoa roi tai len lai")
    doc = (await upload(c, storage, seeded[4], data=data)).json()
    assert (await c.delete(f"/api/v1/documents/{doc['id']}")).status_code == 204
    assert (await upload(c, storage, seeded[4], data=data)).status_code == 201


# --- versions ---------------------------------------------------------------------------------


async def new_version(
    c: httpx.AsyncClient, storage: MemoryStorage, doc: dict, data: bytes, name: str = "v2.pdf"
) -> httpx.Response:
    req = await c.post(
        "/api/v1/documents/upload-url",
        json={
            "file_name": name,
            "mime_type": PDF,
            "size_bytes": len(data),
            "parent_document_id": doc["id"],
        },
    )
    assert req.status_code == 200, req.text
    info = req.json()
    storage.put(info["file_key"], data)
    return await c.post(
        f"/api/v1/documents/{doc['id']}/versions",
        json={
            "document_id": info["document_id"],
            "file_key": info["file_key"],
            "file_name": name,
            "mime_type": PDF,
            "size_bytes": len(data),
        },
    )


async def test_new_version_supersedes_but_keeps_history(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    v1 = (await upload(c, storage, seeded[4])).json()
    resp = await new_version(c, storage, v1, make_text_pdf("phien ban hai da sua"))
    assert resp.status_code == 201, resp.text
    v2 = resp.json()
    assert (v2["version"], v2["is_current"], v2["title"], v2["doc_type"]) == (
        2,
        True,
        "Bảo lãnh tạm ứng",
        "guarantee_advance",
    )
    key = (
        await session.execute(select(Document.file_key).where(Document.id == v2["id"]))
    ).scalar_one()
    assert "/v2/" in key

    detail = (await c.get(f"/api/v1/documents/{v1['id']}")).json()
    assert detail["is_current"] is False  # the old one is still readable
    assert [(v["version"], v["is_current"]) for v in detail["versions"]] == [(2, True), (1, False)]

    current = (await c.get("/api/v1/documents", params={"package_id": str(seeded[4].id)})).json()
    assert [d["id"] for d in current["items"]] == [v2["id"]]
    everything = (
        await c.get(
            "/api/v1/documents", params={"package_id": str(seeded[4].id), "current_only": "false"}
        )
    ).json()
    assert everything["total"] == 2
    # an old version cannot be superseded again: refused already when asking for the URL
    stale = await c.post(
        "/api/v1/documents/upload-url",
        json={
            "file_name": "x.pdf",
            "mime_type": PDF,
            "size_bytes": 5,
            "parent_document_id": v1["id"],
        },
    )
    assert stale.status_code == 409


async def test_deleting_the_latest_version_restores_the_previous_one(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    v1 = (await upload(c, storage, seeded[4])).json()
    v2 = (await new_version(c, storage, v1, make_text_pdf("ban hai"))).json()
    assert (await c.delete(f"/api/v1/documents/{v2['id']}")).status_code == 204
    assert (await c.get(f"/api/v1/documents/{v1['id']}")).json()["is_current"] is True


async def test_version_of_missing_or_duplicate_content(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    data = make_text_pdf("giong het")
    v1 = (await upload(c, storage, seeded[4], data=data)).json()
    assert (await new_version(c, storage, v1, data)).status_code == 409  # identical bytes
    ghost = str(uuid.uuid4())
    body = {"file_name": "a.pdf", "mime_type": PDF, "size_bytes": 5, "parent_document_id": ghost}
    assert (await c.post("/api/v1/documents/upload-url", json=body)).status_code == 404


# --- search -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    ["bao lanh tam ung", "Bảo lãnh tạm ứng", "BAO LANH", "lãnh tạm", "tam ung", "bl-001", "tpbank"],
)
async def test_search_finds_titles_with_and_without_diacritics(
    query: str,
    session: AsyncSession,
    seeded: dict[int, Package],
    storage: MemoryStorage,
    make_client_for,
) -> None:
    c = await make_client_for(session, "clerk")
    await upload(c, storage, seeded[6], doc_no="BL-001", tags=["tpbank"])
    await upload(
        c,
        storage,
        seeded[6],
        title="Biên bản nghiệm thu",
        doc_type="acceptance_minutes",
        name="bb.pdf",
    )
    hits = (await c.get("/api/v1/documents", params={"q": query})).json()
    assert [d["title"] for d in hits["items"]] == ["Bảo lãnh tạm ứng"], query


async def test_search_matches_extracted_text_without_diacritics(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    data = docx_bytes("Hợp đồng cung cấp thiết bị", "Nhà thầu: Nguyên Luân")
    resp = await upload(
        c,
        storage,
        seeded[4],
        data=data,
        mime=DOCX,
        name="hd.docx",
        doc_type="contract",
        title="Hợp đồng số 71",
    )
    assert resp.status_code == 201
    for q in ("nguyen luan", "Nguyên Luân", "thiet bi"):
        hits = (await c.get("/api/v1/documents", params={"q": q})).json()
        assert hits["total"] == 1, q
    assert (await c.get("/api/v1/documents", params={"q": "khong co tu nay"})).json()["total"] == 0


async def test_search_treats_wildcards_literally(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    await upload(c, storage, seeded[4])
    assert (await c.get("/api/v1/documents", params={"q": "%"})).json()["total"] == 0
    assert (await c.get("/api/v1/documents", params={"q": "_"})).json()["total"] == 0


async def test_scanned_pdf_is_uploaded_but_flagged_for_ocr_and_corrupt_file_does_not_block(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    scan = (
        await upload(c, storage, seeded[4], data=buf.getvalue(), name="scan.pdf", title="Bản scan")
    ).json()
    bad = (
        await upload(c, storage, seeded[4], data=b"%PDF-broken", name="hong.pdf", title="Tệp hỏng")
    ).json()
    assert (await c.get(f"/api/v1/documents/{scan['id']}")).json()[
        "extraction_status"
    ] == "needs_ocr"
    assert (await c.get(f"/api/v1/documents/{bad['id']}")).json()["extraction_status"] == "failed"
    # metadata search still works for both
    assert (await c.get("/api/v1/documents", params={"q": "ban scan"})).json()["total"] == 1


async def test_listing_filters_and_pagination(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    for i in range(3):
        await upload(c, storage, seeded[4], title=f"Tài liệu {i}", doc_date=f"2026-09-0{i + 1}")
    await upload(c, storage, seeded[6], title="Hóa đơn", doc_type="invoice", name="hd.pdf")
    base = "/api/v1/documents"
    assert (await c.get(base, params={"package_id": str(seeded[4].id)})).json()["total"] == 3
    assert (await c.get(base, params={"category": "payment"})).json()["total"] == 1
    assert (await c.get(base, params={"doc_type": "invoice"})).json()["total"] == 1
    page = (await c.get(base, params={"package_id": str(seeded[4].id), "page_size": 2})).json()
    assert [d["title"] for d in page["items"]] == [
        "Tài liệu 2",
        "Tài liệu 1",
    ]  # newest document date first
    assert (await c.get(base, params={"page_size": 101})).status_code == 422


# --- permissions and sensitive documents ---------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_normal_document_permissions_follow_matrix(
    role: str,
    session: AsyncSession,
    seeded: dict[int, Package],
    storage: MemoryStorage,
    make_client_for,
) -> None:
    c = await make_client_for(session, role)
    body = {
        "file_name": "a.pdf",
        "mime_type": PDF,
        "size_bytes": 5,
        "package_id": str(seeded[4].id),
    }
    resp = await c.post("/api/v1/documents/upload-url", json=body)
    assert resp.status_code == (200 if role in ALL_DOC_WRITERS else 403)
    assert (await c.get("/api/v1/documents")).status_code == 200
    assert (await c.get("/api/v1/doc-types")).status_code == 200


async def make_sensitive_doc(session, seeded, storage, make_client_for) -> dict:
    admin = await make_client_for(session, "admin")
    resp = await upload(
        admin, storage, seeded[5], title="Hồ sơ Công an", doc_type="contract", name="ca.pdf"
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_documents_of_a_sensitive_package_are_forced_sensitive(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    doc = await make_sensitive_doc(session, seeded, storage, make_client_for)
    assert doc["confidentiality"] == "sensitive"


@pytest.mark.parametrize(
    ("role", "sees_without_access"),
    [
        ("admin", True),
        ("director", True),
        ("procurement", False),
        ("technical", False),
        ("cost", False),
        ("onsite", False),
        ("clerk", False),
        ("viewer", False),
    ],
)
async def test_sensitive_documents_are_redacted_for_roles_without_access(
    role: str,
    sees_without_access: bool,
    session: AsyncSession,
    seeded: dict[int, Package],
    storage: MemoryStorage,
    make_client_for,
) -> None:
    doc = await make_sensitive_doc(session, seeded, storage, make_client_for)
    c = (
        await make_client_for(session, role)
        if role != "admin"
        else await make_client_for(session, "admin")
    )
    listing = (await c.get("/api/v1/documents")).json()
    assert listing["total"] == 1  # still counted, so totals stay honest
    row = listing["items"][0]
    detail = await c.get(f"/api/v1/documents/{doc['id']}")
    dl = await c.get(f"/api/v1/documents/{doc['id']}/download-url")
    found = (await c.get("/api/v1/documents", params={"q": "cong an"})).json()["total"]
    if sees_without_access:
        assert row["restricted"] is False and row["title"] == "Hồ sơ Công an"
        assert (detail.status_code, dl.status_code, found) == (200, 200, 1)
    else:
        assert row["restricted"] is True and row["title"] == "Tài liệu hạn chế"
        assert row["file_name"] is None and row["sha256"] is None and row["doc_type"] is None
        assert (detail.status_code, dl.status_code, found) == (403, 403, 0)  # not even via search


@pytest.mark.parametrize("role", ["procurement", "technical"])
async def test_package_access_unlocks_sensitive_documents_for_assigned_roles(
    role: str,
    session: AsyncSession,
    seeded: dict[int, Package],
    storage: MemoryStorage,
    make_client_for,
) -> None:
    doc = await make_sensitive_doc(session, seeded, storage, make_client_for)
    user_client = await make_client_for(session, role)
    user = (await session.execute(select(User).where(User.role == role))).scalar_one()
    assert (await user_client.get(f"/api/v1/documents/{doc['id']}")).status_code == 403

    admin = await make_client_for(session, "admin")
    put = await admin.put(
        f"/api/v1/packages/{seeded[5].id}/access", json={"user_ids": [str(user.id)]}
    )
    assert put.status_code == 200 and [u["id"] for u in put.json()["users"]] == [str(user.id)]
    assert (await user_client.get(f"/api/v1/documents/{doc['id']}")).status_code == 200
    assert (await user_client.get("/api/v1/documents", params={"q": "cong an"})).json()[
        "total"
    ] == 1
    # access is per package: a sensitive doc elsewhere stays hidden
    other = (await session.execute(select(Package).where(Package.number == 4))).scalar_one()
    other.is_sensitive = True
    await session.commit()
    elsewhere = await upload(admin, storage, other, title="Nhạy cảm gói 4", name="g4.pdf")
    assert (await user_client.get(f"/api/v1/documents/{elsewhere.json()['id']}")).status_code == 403
    # revoking closes it again
    await admin.put(f"/api/v1/packages/{seeded[5].id}/access", json={"user_ids": []})
    assert (await user_client.get(f"/api/v1/documents/{doc['id']}")).status_code == 403


async def test_uploading_sensitive_files_requires_access(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    proc = await make_client_for(session, "procurement")
    body = {
        "file_name": "a.pdf",
        "mime_type": PDF,
        "size_bytes": 5,
        "package_id": str(seeded[5].id),
    }
    assert (await proc.post("/api/v1/documents/upload-url", json=body)).status_code == 403
    cost = await make_client_for(session, "cost")
    assert (await cost.post("/api/v1/documents/upload-url", json=body)).status_code == 403
    user = (await session.execute(select(User).where(User.role == "procurement"))).scalar_one()
    session.add(PackageAccess(user_id=user.id, package_id=seeded[5].id))
    await session.commit()
    assert (await proc.post("/api/v1/documents/upload-url", json=body)).status_code == 200


@pytest.mark.parametrize("role", [r for r in ALL_ROLES if r not in {"admin", "director"}])
async def test_only_admin_and_director_manage_access(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    url = f"/api/v1/packages/{seeded[5].id}/access"
    assert (await c.get(url)).status_code == 403
    assert (await c.put(url, json={"user_ids": []})).status_code == 403


async def test_access_assignment_validation_and_audit(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    admin = await make_client_for(session, "admin")
    viewer = await make_user(session, "viewer")
    url = f"/api/v1/packages/{seeded[5].id}/access"
    assert (
        await admin.put(url, json={"user_ids": [str(viewer.id)]})
    ).status_code == 422  # wrong role
    assert (
        await admin.put(url, json={"user_ids": [str(uuid.uuid4())]})
    ).status_code == 422  # unknown
    inactive = await make_user(session, "technical", is_active=False)
    assert (await admin.put(url, json={"user_ids": [str(inactive.id)]})).status_code == 422
    ok = await make_user(session, "procurement", email="p@example.test")
    assert (await admin.put(url, json={"user_ids": [str(ok.id)]})).status_code == 200
    assert (await admin.put(url, json={"user_ids": [str(ok.id)]})).status_code == 200  # idempotent
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "package_access")))
        .scalars()
        .all()
    )
    assert len(rows) == 2 and rows[0].changes["granted"] == [str(ok.id)]


# --- download, edit, delete ---------------------------------------------------------------------


async def test_download_url_is_audited_and_inline_only_for_previewable_types(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    pdf = (await upload(c, storage, seeded[4])).json()
    word = (
        await upload(
            c,
            storage,
            seeded[4],
            data=docx_bytes("x y z"),
            mime=DOCX,
            name="a.docx",
            title="Biên bản",
            doc_type="other",
        )
    ).json()
    a = (
        await c.get(f"/api/v1/documents/{pdf['id']}/download-url", params={"inline": "true"})
    ).json()
    b = (
        await c.get(f"/api/v1/documents/{word['id']}/download-url", params={"inline": "true"})
    ).json()
    assert (
        a["inline"] is True and a["expires_in"] == 300 and a["url"].startswith("memory://download/")
    )
    assert b["inline"] is False  # Word/Excel are download-only (SPEC 4.6)
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "download")))
        .scalars()
        .all()
    )
    assert len(rows) == 2 and all(r.user_id is not None for r in rows)
    assert {r.entity_id for r in rows} == {pdf["id"], word["id"]}


async def test_patch_metadata_reindexes_and_derives_category(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    doc = (await upload(c, storage, seeded[4], doc_type="other", title="Tài liệu tạm")).json()
    assert doc["category"] == "other"
    upd = await c.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"title": "Biên bản nghiệm thu", "doc_type": "acceptance_minutes", "tags": ["qd-9"]},
    )
    assert upd.status_code == 200
    assert (upd.json()["category"], upd.json()["tags"]) == ("acceptance", ["qd-9"])
    assert (await c.get("/api/v1/documents", params={"q": "bien ban nghiem thu"})).json()[
        "total"
    ] == 1
    assert (await c.get("/api/v1/documents", params={"q": "tai lieu tam"})).json()["total"] == 0
    assert (await c.get("/api/v1/documents", params={"q": "qd-9"})).json()["total"] == 1
    for bad in ({"title": None}, {"doc_type": "nope"}, {"title": ""}, {"category": "bogus"}):
        assert (await c.patch(f"/api/v1/documents/{doc['id']}", json=bad)).status_code == 422
    audit_rows = (
        (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "document", AuditLog.action == "update"
                )
            )
        )
        .scalars()
        .all()
    )
    assert audit_rows and audit_rows[0].changes["title"]["after"] == "Biên bản nghiệm thu"


async def test_only_governors_change_confidentiality_and_sensitive_packages_stay_sensitive(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    clerk = await make_client_for(session, "clerk")
    admin = await make_client_for(session, "admin")
    doc = (await upload(clerk, storage, seeded[4])).json()
    url = f"/api/v1/documents/{doc['id']}"
    assert (await clerk.patch(url, json={"confidentiality": "sensitive"})).status_code == 403
    assert (await admin.patch(url, json={"confidentiality": "sensitive"})).json()[
        "confidentiality"
    ] == "sensitive"
    # once sensitive, the clerk can no longer even open it
    assert (await clerk.get(url)).status_code == 403
    sens = await make_sensitive_doc(session, seeded, storage, make_client_for)
    back = await admin.patch(f"/api/v1/documents/{sens['id']}", json={"confidentiality": "normal"})
    assert back.status_code == 409


async def test_delete_is_soft_and_audited(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    doc = (await upload(c, storage, seeded[4])).json()
    assert (await c.delete(f"/api/v1/documents/{doc['id']}")).status_code == 204
    assert (await c.get(f"/api/v1/documents/{doc['id']}")).status_code == 404
    assert (await c.delete(f"/api/v1/documents/{doc['id']}")).status_code == 404
    assert (await c.get("/api/v1/documents")).json()["total"] == 0
    row = (await session.execute(select(Document).where(Document.id == doc["id"]))).scalar_one()
    assert row.deleted_at is not None  # kept for the audit trail
    assert (
        await session.execute(
            select(AuditLog).where(AuditLog.action == "delete", AuditLog.entity_type == "document")
        )
    ).scalar_one()


async def test_viewer_cannot_write_and_unauthenticated_is_401(
    session: AsyncSession,
    seeded: dict[int, Package],
    storage: MemoryStorage,
    make_client_for,
    client: httpx.AsyncClient,
) -> None:
    viewer = await make_client_for(session, "viewer")
    clerk = await make_client_for(session, "clerk")
    doc = (await upload(clerk, storage, seeded[4])).json()
    url = f"/api/v1/documents/{doc['id']}"
    assert (await viewer.get(url)).status_code == 200
    assert (await viewer.patch(url, json={"title": "x"})).status_code == 403
    assert (await viewer.delete(url)).status_code == 403
    assert (await client.get("/api/v1/documents")).status_code == 401


# --- misc ---------------------------------------------------------------------------------------


async def test_doc_types_cover_spec_codes_with_categories(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    types = {t["code"]: t for t in (await c.get("/api/v1/doc-types")).json()}
    assert {
        "decision_invest",
        "guarantee_advance",
        "coc_cq",
        "photo",
        "other",
        "settlement_checklist",
    } <= set(types)
    assert types["guarantee_advance"]["category"] == "contract" and len(types) >= 35


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Bảo lãnh tạm ứng số 1.pdf", "bao-lanh-tam-ung-so-1.pdf"),
        ("Đề cương TVQLDA (bản 2).DOCX", "de-cuong-tvqlda-ban-2.docx"),
        ("../../etc/passwd", "etc-passwd"),
        ("  .hidden  ", "hidden"),
        ("no_extension", "no_extension"),
        ("!!!.pdf", "file.pdf"),
    ],
)
def test_safe_filename(raw: str, expected: str) -> None:
    assert safe_filename(raw) == expected
