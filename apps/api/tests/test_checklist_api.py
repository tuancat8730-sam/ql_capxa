"""M4: per-package document checklist (SPEC 4.7, 14.8)."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChecklistItem, ChecklistTemplate, Package
from app.seed.checklists import CONSULTING, GOODS, seed_checklist_templates, seed_checklists
from app.seed.project import seed_project
from app.services.storage import MemoryStorage
from tests.conftest import ALL_ROLES
from tests.test_documents_api import upload

TODAY = date(2026, 10, 6)


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    await seed_checklists(session)
    return {p.number: p for p in (await session.execute(select(Package))).scalars().all()}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.checklists.today_local", lambda: TODAY)


async def checklist(c, package: Package) -> dict:
    resp = await c.get(f"/api/v1/packages/{package.id}/checklist")
    assert resp.status_code == 200, resp.text
    return resp.json()


def item(data: dict, title: str) -> dict:
    return next(i for i in data["items"] if i["title"] == title)


# --- seed ------------------------------------------------------------------------------------


async def test_templates_match_spec_4_7(session: AsyncSession, seeded: dict[int, Package]) -> None:
    counts = dict(
        (
            await session.execute(
                select(ChecklistTemplate.package_type, func.count()).group_by(
                    ChecklistTemplate.package_type
                )
            )
        ).all()
    )
    assert counts == {"goods": len(GOODS), "consulting": len(CONSULTING)}


async def test_seed_is_idempotent(session: AsyncSession, seeded: dict[int, Package]) -> None:
    await seed_checklist_templates(session)
    await seed_checklists(session)
    templates = (
        await session.execute(select(func.count()).select_from(ChecklistTemplate))
    ).scalar_one()
    items = (await session.execute(select(func.count()).select_from(ChecklistItem))).scalar_one()
    goods_pkgs = sum(1 for p in seeded.values() if p.package_type == "goods")
    consulting_pkgs = len(seeded) - goods_pkgs
    assert templates == len(GOODS) + len(CONSULTING)
    assert items == goods_pkgs * len(GOODS) + consulting_pkgs * len(CONSULTING)


async def test_items_follow_the_package_type_and_stage_order(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    goods = await checklist(c, seeded[4])
    consulting = await checklist(c, seeded[6])
    assert len(goods["items"]) == len(GOODS) and len(consulting["items"]) == len(CONSULTING)
    stages = [i["stage_code"] for i in goods["items"]]
    order = ["S2_SELECTION", "S3_EXECUTION", "S4_ACCEPTANCE", "S5_PAYMENT_SETTLEMENT"]
    assert stages == sorted(stages, key=order.index)
    assert all(i["status"] == "missing" for i in goods["items"])
    assert goods["completion_pct"] == 0 and goods["required_done"] == 0


async def test_due_dates_come_from_the_contract_start(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = await checklist(c, seeded[4])  # contract signed 14/09/2026
    assert item(data, "Bảo lãnh thực hiện hợp đồng")["due_date"] == "2026-09-21"  # start + 7
    assert item(data, "Bảo lãnh tạm ứng")["due_date"] == "2026-09-14"
    assert item(data, "Hợp đồng")["due_date"] is None
    no_contract = await checklist(c, seeded[3])
    assert all(i["due_date"] is None for i in no_contract["items"])


async def test_overdue_flag_only_for_missing_required_items(
    session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = await checklist(c, seeded[4])  # "today" is 06/10/2026
    assert item(data, "Bảo lãnh thực hiện hợp đồng")["overdue"] is True
    assert item(data, "Hợp đồng")["overdue"] is False  # no due date


# --- linking documents -----------------------------------------------------------------------


async def test_uploading_a_matching_type_receives_the_checklist_item(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    resp = await upload(
        c, storage, seeded[4], doc_type="contract", title="Hợp đồng số 71", name="hd71.pdf"
    )
    doc = resp.json()
    data = await checklist(c, seeded[4])
    it = item(data, "Hợp đồng")
    assert (it["status"], it["document_id"], it["document_title"]) == (
        "received",
        doc["id"],
        "Hợp đồng số 71",
    )
    assert data["required_done"] == 1
    required = [i for i in data["items"] if i["required"]]
    assert data["required_total"] == len(required)
    assert data["completion_pct"] == round(1 / len(required) * 100, 1)
    # a second document of the same type does not steal another item
    second = await upload(
        c, storage, seeded[4], doc_type="contract", title="Hợp đồng bản 2", name="hd71b.pdf"
    )
    assert second.status_code == 201
    assert (await checklist(c, seeded[4]))["required_done"] == 1


async def test_a_new_version_moves_the_link_and_deleting_it_moves_it_back(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    from tests.test_documents_api import new_version
    from tests.test_extract import make_text_pdf

    c = await make_client_for(session, "clerk")
    v1 = (
        await upload(c, storage, seeded[4], doc_type="invoice", title="Hóa đơn", name="hd.pdf")
    ).json()
    v2 = (await new_version(c, storage, v1, make_text_pdf("hoa don ban sua"))).json()
    assert item(await checklist(c, seeded[4]), "Hóa đơn")["document_id"] == v2["id"]
    await c.delete(f"/api/v1/documents/{v2['id']}")
    after = item(await checklist(c, seeded[4]), "Hóa đơn")
    assert (after["status"], after["document_id"]) == ("received", v1["id"])
    await c.delete(f"/api/v1/documents/{v1['id']}")
    gone = item(await checklist(c, seeded[4]), "Hóa đơn")
    assert (gone["status"], gone["document_id"]) == ("missing", None)


async def test_instantiate_links_documents_uploaded_before_the_checklist_existed(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    await session.execute(
        ChecklistItem.__table__.delete().where(ChecklistItem.package_id == seeded[6].id)
    )
    await session.commit()
    c = await make_client_for(session, "clerk")
    await upload(
        c, storage, seeded[6], doc_type="contract", title="Hợp đồng TVQLDA", name="hd80.pdf"
    )
    assert (await checklist(c, seeded[6]))["items"] == []
    resp = await c.post(f"/api/v1/packages/{seeded[6].id}/checklist/instantiate")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == len(CONSULTING)
    assert item(data, "Hợp đồng")["status"] == "received"
    again = await c.post(f"/api/v1/packages/{seeded[6].id}/checklist/instantiate")
    assert len(again.json()["items"]) == len(CONSULTING)  # idempotent


# --- editing items ---------------------------------------------------------------------------


async def test_patch_item_status_rules(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    c = await make_client_for(session, "clerk")
    data = await checklist(c, seeded[4])
    target = item(data, "Hóa đơn")
    url = f"/api/v1/checklist-items/{target['id']}"

    na = await c.patch(url, json={"status": "not_applicable", "note": "Chưa phát sinh"})
    assert (na.json()["status"], na.json()["note"]) == ("not_applicable", "Chưa phát sinh")
    after = await checklist(c, seeded[4])
    required = [i for i in after["items"] if i["required"] and i["status"] != "not_applicable"]
    assert after["required_total"] == len(required)  # N/A items leave the denominator

    assert (await c.patch(url, json={"status": "received"})).status_code == 422  # needs a document
    assert (await c.patch(url, json={"status": None})).status_code == 422

    doc = (
        await upload(
            c, storage, seeded[4], doc_type="other", title="Hóa đơn đã nhận", name="inv.pdf"
        )
    ).json()
    linked = await c.patch(url, json={"document_id": doc["id"]})
    assert (linked.json()["status"], linked.json()["document_title"]) == (
        "received",
        "Hóa đơn đã nhận",
    )
    cleared = await c.patch(url, json={"status": "missing"})
    assert (cleared.json()["status"], cleared.json()["document_id"]) == ("missing", None)

    other_pkg_doc = (
        await upload(c, storage, seeded[6], doc_type="other", title="Gói khác", name="o.pdf")
    ).json()
    assert (await c.patch(url, json={"document_id": other_pkg_doc["id"]})).status_code == 422
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (
        await c.patch(f"/api/v1/checklist-items/{ghost}", json={"note": "x"})
    ).status_code == 404
    assert (await c.patch(url, json={"due_date": "2026-12-31"})).json()["due_date"] == "2026-12-31"


async def test_package_404s(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "clerk")
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (await c.get(f"/api/v1/packages/{ghost}/checklist")).status_code == 404
    assert (await c.post(f"/api/v1/packages/{ghost}/checklist/instantiate")).status_code == 404


# --- permissions and sensitive documents -----------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_checklist_permissions_follow_the_document_matrix(
    role: str, session: AsyncSession, seeded: dict[int, Package], make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get(f"/api/v1/packages/{seeded[4].id}/checklist")).status_code == 200
    target = (await checklist(c, seeded[4]))["items"][0]["id"]
    writable = role != "viewer"
    assert (await c.patch(f"/api/v1/checklist-items/{target}", json={"note": "n"})).status_code == (
        200 if writable else 403
    )
    inst = await c.post(f"/api/v1/packages/{seeded[4].id}/checklist/instantiate")
    assert inst.status_code == (200 if writable else 403)


async def test_restricted_documents_do_not_leak_their_titles_through_the_checklist(
    session: AsyncSession, seeded: dict[int, Package], storage: MemoryStorage, make_client_for
) -> None:
    admin = await make_client_for(session, "admin")
    viewer = await make_client_for(session, "viewer")
    resp = await upload(
        admin, storage, seeded[5], doc_type="contract", title="Hợp đồng Công an", name="ca.pdf"
    )
    assert resp.status_code == 201
    as_admin = item(await checklist(admin, seeded[5]), "Hợp đồng")
    as_viewer = item(await checklist(viewer, seeded[5]), "Hợp đồng")
    assert (
        as_admin["document_title"] == "Hợp đồng Công an"
        and as_admin["document_restricted"] is False
    )
    assert as_viewer["status"] == "received"  # the progress is visible...
    assert (
        as_viewer["document_title"] is None and as_viewer["document_restricted"] is True
    )  # ...the title is not
