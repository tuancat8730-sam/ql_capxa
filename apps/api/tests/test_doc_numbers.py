"""M8: outgoing document numbers (SPEC 3.23, 4.15)."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, OutgoingDocNumber
from app.routers.doc_numbers import format_doc_no
from tests.conftest import ALL_ROLES

URL = "/api/v1/outgoing-doc-numbers"
READERS = {"admin", "director", "procurement", "technical", "cost", "clerk", "viewer"}
WRITERS = {"admin", "clerk"}


def body(kind: str = "CV", subject: str = "V/v đề nghị bổ sung hồ sơ", **over) -> dict:
    return {"doc_kind": kind, "subject": subject, **over}


def test_format_matches_the_spec_example() -> None:
    assert format_doc_no(12, "CV") == "012/CV-QLDA-SGM"
    assert format_doc_no(1234, "BC") == "1234/BC-QLDA-SGM"


async def test_numbers_count_up_per_kind_and_year(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "clerk")
    nos = [(await c.post(URL, json=body("CV", issued_date="2026-03-01"))).json() for _ in range(3)]
    assert [n["doc_no"] for n in nos] == ["001/CV-QLDA-SGM", "002/CV-QLDA-SGM", "003/CV-QLDA-SGM"]
    assert nos[0]["year"] == 2026 and nos[0]["created_by_name"] == "User clerk"

    other_kind = (await c.post(URL, json=body("BC", issued_date="2026-03-02"))).json()
    assert other_kind["doc_no"] == "001/BC-QLDA-SGM"  # each kind has its own sequence
    next_year = (await c.post(URL, json=body("CV", issued_date="2027-01-04"))).json()
    assert (next_year["year"], next_year["doc_no"]) == (2027, "001/CV-QLDA-SGM")
    again = (await c.post(URL, json=body("CV", issued_date="2026-12-31"))).json()
    assert again["doc_no"] == "004/CV-QLDA-SGM"  # the 2026 sequence goes on


async def test_issue_date_defaults_to_today(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    r = await c.post(URL, json=body())
    assert r.status_code == 201 and r.json()["issued_date"] and r.json()["year"] >= 2026


async def test_concurrent_requests_never_share_a_number(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    replies = await asyncio.gather(
        *(c.post(URL, json=body(issued_date="2026-05-05")) for _ in range(8))
    )
    assert all(r.status_code == 201 for r in replies)
    seqs = sorted(r.json()["seq"] for r in replies)
    assert seqs == list(range(1, 9))


async def test_validation(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "clerk")
    assert (await c.post(URL, json=body("XX"))).status_code == 422  # unknown kind
    assert (await c.post(URL, json=body(subject="  "))).status_code == 422
    assert (await c.post(URL, json=body(subject="x" * 501))).status_code == 422
    assert (await c.post(URL, json={"doc_kind": "CV"})).status_code == 422
    assert (await c.post(URL, json=body(issued_date="not-a-date"))).status_code == 422
    assert (await session.execute(select(OutgoingDocNumber))).first() is None


async def test_list_filters_and_search_without_accents(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    await c.post(URL, json=body("CV", "Đề nghị bảo lãnh tạm ứng", issued_date="2026-01-05"))
    await c.post(URL, json=body("BC", "Báo cáo tuần", issued_date="2026-01-06"))
    await c.post(URL, json=body("CV", "Công văn năm sau", issued_date="2027-01-06"))

    everything = (await c.get(URL)).json()
    assert everything["total"] == 3 and everything["items"][0]["year"] == 2027  # newest year first
    assert (await c.get(URL, params={"year": 2026})).json()["total"] == 2
    assert (await c.get(URL, params={"doc_kind": "BC"})).json()["total"] == 1
    found = (await c.get(URL, params={"q": "bao lanh tam ung"})).json()
    assert [i["subject"] for i in found["items"]] == ["Đề nghị bảo lãnh tạm ứng"]
    assert (await c.get(URL, params={"q": "001/CV"})).json()["total"] == 2
    assert (await c.get(URL, params={"q": "%"})).json()["total"] == 0
    assert (await c.get(URL, params={"doc_kind": "ZZ"})).status_code == 422


async def test_role_matrix(session: AsyncSession, make_client_for) -> None:
    for role in ALL_ROLES:
        c = await make_client_for(session, role)
        assert (await c.get(URL)).status_code == (200 if role in READERS else 403), role
        r = await c.post(URL, json=body(issued_date="2026-06-06"))
        assert r.status_code == (201 if role in WRITERS else 403), role


async def test_unauthenticated(client) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.post(URL, json=body())).status_code == 401


async def test_issuing_a_number_is_audited(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "clerk")
    created = (await c.post(URL, json=body(issued_date="2026-06-06"))).json()
    row = (
        await session.execute(select(AuditLog).where(AuditLog.entity_id == created["id"]))
    ).scalar_one()
    assert row.action == "create" and row.changes["doc_no"] == "001/CV-QLDA-SGM"
