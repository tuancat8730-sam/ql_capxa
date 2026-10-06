"""M8: global search (SPEC 4.16) - grouped hits, snippets, accent-free, sensitive files hidden."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Package, PackageAccess, Project, User
from app.seed.project import seed_project
from app.seed.risks import seed_risks
from app.services.documents import refresh_search_vector
from app.services.search import escape_like, first_snippet, fold, snippet
from tests.conftest import ALL_ROLES

# --- helpers -----------------------------------------------------------------------------------


def test_fold_strips_vietnamese_marks_and_keeps_length() -> None:
    text = "Bảo lãnh tạm ứng ĐẶC BIỆT"
    assert fold(text) == "bao lanh tam ung dac biet"
    assert len(fold(text)) == len(text)


def test_snippet_cuts_around_the_match_from_the_accented_text() -> None:
    text = "Đoạn đầu " * 20 + "Bảo lãnh tạm ứng hết hạn " + "đoạn cuối " * 20
    found = snippet(text, "bao lanh tam ung", width=10)
    assert found is not None
    assert "Bảo lãnh tạm ứng" in found and found.startswith("…") and found.endswith("…")
    assert snippet("không có gì", "xyz") is None
    assert snippet(None, "x") is None and snippet("abc", "  ") is None


def test_snippet_without_ellipsis_when_the_text_is_short() -> None:
    assert snippet("Hợp đồng số 71", "hop dong") == "Hợp đồng số 71"


def test_first_snippet_skips_fields_without_a_match() -> None:
    found = first_snippet("lap thinh", None, "Gói 01", "Nhà thầu An Lập Thịnh")
    assert found == "Nhà thầu An Lập Thịnh"
    assert first_snippet("zzz", "a", None) is None


def test_escape_like_makes_wildcards_literal() -> None:
    assert escape_like("50%_a\\") == "50\\%\\_a\\\\"


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    await seed_risks(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


async def add_document(
    session: AsyncSession, package: Package, title: str, confidentiality: str = "normal"
) -> Document:
    project = (await session.execute(select(Project))).scalars().first()
    assert project
    doc = Document(
        project_id=project.id,
        package_id=package.id,
        category="contract",
        doc_type="contract",
        title=title,
        confidentiality=confidentiality,
        file_key=f"k/{title}",
        file_name=f"{title}.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256="0" * 64,
        text_content="Nội dung có cụm từ bảo lãnh đặc biệt trong điều khoản",
    )
    session.add(doc)
    await session.flush()
    await refresh_search_vector(session, doc.id)
    await session.commit()
    return doc


def kinds(data: dict) -> dict[str, dict]:
    return {g["kind"]: g for g in data["groups"]}


async def test_requires_login_and_a_query_of_two_characters(
    session: AsyncSession, seeded: dict[int, Package], client, make_client_for
) -> None:
    assert (await client.get("/api/v1/search", params={"q": "gói"})).status_code == 401
    c = await make_client_for(session, "viewer")
    assert (await c.get("/api/v1/search")).status_code == 422
    assert (await c.get("/api/v1/search", params={"q": "g"})).status_code == 422
    assert (await c.get("/api/v1/search", params={"q": "x" * 101})).status_code == 422
    assert (await c.get("/api/v1/search", params={"q": "gói", "limit": 0})).status_code == 422


async def test_finds_a_package_by_contractor_without_accents(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/search", params={"q": "an lap thinh"})).json()
    group = kinds(data)["package"]
    assert group["total"] == 1
    hit = group["items"][0]
    assert hit["package_number"] == 1 and hit["title"].startswith("Gói 01")
    assert hit["package_id"] == str(seeded[1].id) and "An Lập Thịnh" in hit["snippet"]
    assert data["query"] == "an lap thinh"


async def test_finds_contracts_and_risks_and_groups_them_by_kind(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "director")
    contracts = kinds((await c.get("/api/v1/search", params={"q": "73"})).json()).get("contract")
    assert contracts and any(i["title"] == "Hợp đồng 73" for i in contracts["items"])

    data = (await c.get("/api/v1/search", params={"q": "bao lanh"})).json()
    risk = kinds(data)["risk"]
    assert risk["total"] >= 1 and risk["items"][0]["title"].startswith("R-")
    assert all(i["kind"] == "risk" for i in risk["items"])


async def test_limit_caps_the_items_but_total_counts_everything(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/search", params={"q": "gói", "limit": 2})).json()
    group = kinds(data)["package"]
    assert group["total"] == 8 and len(group["items"]) == 2


async def test_unmatched_query_returns_no_groups(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/search", params={"q": "zzzkhongco"})).json()
    assert data["groups"] == []


async def test_percent_in_the_query_is_literal(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    assert (await c.get("/api/v1/search", params={"q": "%%"})).json()["groups"] == []


async def test_documents_are_found_with_an_excerpt_from_the_extracted_text(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    await add_document(session, seeded[4], "Hợp đồng ký")
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/search", params={"q": "bao lanh dac biet"})).json()
    hit = kinds(data)["document"]["items"][0]
    assert hit["title"] == "Hợp đồng ký" and hit["package_number"] == 4
    assert "bảo lãnh đặc biệt" in hit["snippet"]


async def test_sensitive_documents_never_leak_through_search(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    await add_document(session, seeded[4], "Biên bản mật", "sensitive")
    for role in ALL_ROLES:
        c = await make_client_for(session, role)
        data = (await c.get("/api/v1/search", params={"q": "mat"})).json()
        titles = [i["title"] for g in data["groups"] for i in g["items"]]
        sees = role in {"admin", "director"}  # technical/procurement need package_access
        assert ("Biên bản mật" in titles) is sees, role


async def test_assigned_technical_user_sees_the_sensitive_document(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    await add_document(session, seeded[4], "Biên bản mật", "sensitive")
    c = await make_client_for(session, "technical")
    user = (await session.execute(select(User).where(User.role == "technical"))).scalars().one()
    session.add(PackageAccess(user_id=user.id, package_id=seeded[4].id))
    await session.commit()
    data = (await c.get("/api/v1/search", params={"q": "mat"})).json()
    assert "Biên bản mật" in [i["title"] for g in data["groups"] for i in g["items"]]


async def test_roles_without_risk_access_get_no_risk_or_issue_groups(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    clerk = await make_client_for(session, "clerk")  # no access to the risk register
    assert "risk" not in kinds((await clerk.get("/api/v1/search", params={"q": "gói"})).json())
    viewer = await make_client_for(session, "viewer")
    assert "risk" in kinds((await viewer.get("/api/v1/search", params={"q": "gói"})).json())
