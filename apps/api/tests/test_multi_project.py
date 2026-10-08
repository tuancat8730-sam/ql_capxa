"""Several projects at once: who sees which, and that their data never mixes."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AuditLog, Package, Project, ProjectMember, User
from tests.conftest import login, make_user

H = "X-Project-Id"


async def make_project(
    session: AsyncSession, code: str, project_type: str = "procurement"
) -> Project:
    project = Project(code=code, name=f"Dự án {code}", project_type=project_type)
    session.add(project)
    await session.commit()
    return project


async def make_package(session: AsyncSession, project: Project, number: int = 1) -> Package:
    package = Package(
        project_id=project.id,
        number=number,
        name=f"Gói {number} của {project.code}",
        package_type="goods",
    )
    session.add(package)
    await session.commit()
    return package


async def seat(session: AsyncSession, project: Project, user: User, role: str) -> None:
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))
    await session.commit()


async def client_as(
    storage, session: AsyncSession, email: str, role: str
) -> tuple[httpx.AsyncClient, User]:
    from app.main import create_app

    user = await make_user(session, role, email=email, seat=False)
    c = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(storage=storage)), base_url="http://test"
    )
    resp = await login(c, email)
    c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return c, user


@pytest.fixture
async def two_projects(session: AsyncSession) -> tuple[Project, Project]:
    return await make_project(session, "A"), await make_project(session, "B")


async def test_my_projects_lists_only_the_ones_the_user_is_seated_in(
    session: AsyncSession, storage, two_projects
) -> None:
    a, _ = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    resp = await c.get("/api/v1/projects")
    assert resp.status_code == 200
    rows = resp.json()
    assert [r["code"] for r in rows] == ["A"]
    assert rows[0]["role"] == "director"
    assert "packages" in rows[0]["modules"]


async def test_system_admin_sees_every_project(
    session: AsyncSession, storage, two_projects
) -> None:
    c, _ = await client_as(storage, session, "root@example.test", "admin")
    codes = [r["code"] for r in (await c.get("/api/v1/projects")).json()]
    assert codes == ["A", "B"]


async def test_modules_follow_the_project_type(session: AsyncSession, storage) -> None:
    await make_project(session, "SW", "software_delivery")
    c, _ = await client_as(storage, session, "root@example.test", "admin")
    modules = (await c.get("/api/v1/projects")).json()[0]["modules"]
    assert "schedule" in modules and "packages" not in modules


async def test_only_a_system_admin_creates_projects(session: AsyncSession, storage) -> None:
    body = {"code": "NEW", "name": "Dự án mới", "project_type": "software_delivery"}
    director, _ = await client_as(storage, session, "v@example.test", "director")
    assert (await director.post("/api/v1/projects", json=body)).status_code == 403
    admin, _ = await client_as(storage, session, "root@example.test", "admin")
    created = await admin.post("/api/v1/projects", json=body)
    assert created.status_code == 201
    assert created.json()["project_type"] == "software_delivery"
    assert (await admin.post("/api/v1/projects", json=body)).status_code == 409


async def test_two_seats_without_a_header_is_ambiguous(
    session: AsyncSession, storage, two_projects
) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    await seat(session, b, user, "director")
    assert (await c.get("/api/v1/packages")).status_code == 400
    assert (await c.get("/api/v1/packages", headers={H: str(a.id)})).status_code == 200


async def test_a_project_the_user_is_not_seated_in_is_refused(
    session: AsyncSession, storage, two_projects
) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    assert (await c.get("/api/v1/packages", headers={H: str(b.id)})).status_code == 403
    assert (await c.get("/api/v1/packages", headers={H: str(uuid.uuid4())})).status_code == 404
    assert (await c.get("/api/v1/packages", headers={H: "nope"})).status_code == 400


async def test_a_user_with_no_seat_gets_nothing(session: AsyncSession, storage) -> None:
    c, _ = await client_as(storage, session, "x@example.test", "viewer")
    await make_project(session, "A")
    assert (await c.get("/api/v1/projects")).json() == []
    assert (await c.get("/api/v1/packages")).status_code == 403


async def test_packages_never_cross_projects(session: AsyncSession, storage, two_projects) -> None:
    a, b = two_projects
    pa, pb = await make_package(session, a), await make_package(session, b)
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    await seat(session, b, user, "director")

    in_a = (await c.get("/api/v1/packages", headers={H: str(a.id)})).json()
    assert [p["id"] for p in in_a["items"]] == [str(pa.id)]
    # a package of project B is invisible and untouchable through project A
    other = {H: str(a.id)}
    assert (await c.get(f"/api/v1/packages/{pb.id}", headers=other)).status_code == 404
    patched = await c.patch(f"/api/v1/packages/{pb.id}", json={"name": "x"}, headers=other)
    assert patched.status_code == 404
    assert (await c.get(f"/api/v1/packages/{pb.id}/checklist", headers=other)).status_code == 404
    assert (await c.get(f"/api/v1/packages/{pb.id}/contracts", headers=other)).status_code == 404
    assert (await c.get(f"/api/v1/packages/{pb.id}", headers={H: str(b.id)})).status_code == 200


async def test_risk_codes_restart_in_each_project(
    session: AsyncSession, storage, two_projects
) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    await seat(session, b, user, "director")
    body = {"title": "Rủi ro", "category": "supply", "probability": 3, "impact": 3}
    first = await c.post("/api/v1/risks", json=body, headers={H: str(a.id)})
    second = await c.post("/api/v1/risks", json=body, headers={H: str(b.id)})
    assert first.status_code == second.status_code == 201
    assert first.json()["code"] == second.json()["code"] == "R-001"
    # each project lists only its own
    for project, risk in ((a, first), (b, second)):
        listed = (await c.get("/api/v1/risks", headers={H: str(project.id)})).json()
        assert [r["id"] for r in listed["items"]] == [risk.json()["id"]]
    # and cannot reach the other's by id
    got = await c.get(f"/api/v1/risks/{second.json()['id']}", headers={H: str(a.id)})
    assert got.status_code == 404


async def test_the_role_is_per_project(session: AsyncSession, storage, two_projects) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    await seat(session, b, user, "viewer")
    body = {"title": "Rủi ro", "category": "supply", "probability": 3, "impact": 3}
    assert (await c.post("/api/v1/risks", json=body, headers={H: str(a.id)})).status_code == 201
    assert (await c.post("/api/v1/risks", json=body, headers={H: str(b.id)})).status_code == 403
    assert (await c.get("/api/v1/risks", headers={H: str(b.id)})).status_code == 200


async def test_issues_meetings_and_doc_numbers_are_per_project(
    session: AsyncSession, storage, two_projects
) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "admin")
    await seat(session, a, user, "admin")
    await seat(session, b, user, "admin")
    ha, hb = {H: str(a.id)}, {H: str(b.id)}

    issue = {"issue_type": "operational", "level": 1, "title": "Vướng mắc"}
    ia = await c.post("/api/v1/issues", json=issue, headers=ha)
    ib = await c.post("/api/v1/issues", json=issue, headers=hb)
    assert ia.status_code == ib.status_code == 201
    assert ia.json()["code"] == ib.json()["code"]
    assert (await c.get(f"/api/v1/issues/{ib.json()['id']}", headers=ha)).status_code == 404

    meeting = {"meeting_type": "weekly", "meeting_date": "2026-10-01"}
    ma = await c.post("/api/v1/meetings", json=meeting, headers=ha)
    assert ma.status_code == 201
    listed_b = (await c.get("/api/v1/meetings", headers=hb)).json()
    assert listed_b["total"] == 0
    assert (
        await c.get(f"/api/v1/meetings/{ma.json()['id']}/action-items", headers=hb)
    ).status_code == 404

    num = {"doc_kind": "CV", "subject": "Công văn", "issued_date": "2026-10-01"}
    na = await c.post("/api/v1/outgoing-doc-numbers", json=num, headers=ha)
    nb = await c.post("/api/v1/outgoing-doc-numbers", json=num, headers=hb)
    assert na.json()["seq"] == nb.json()["seq"] == 1
    assert (await c.get("/api/v1/outgoing-doc-numbers", headers=ha)).json()["total"] == 1


async def test_audit_rows_carry_their_project(session: AsyncSession, storage, two_projects) -> None:
    a, b = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    await seat(session, b, user, "director")
    body = {"title": "Rủi ro", "category": "supply", "probability": 3, "impact": 3}
    await c.post("/api/v1/risks", json=body, headers={H: str(b.id)})
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_type == "risk")))
        .scalars()
        .all()
    )
    assert [r.project_id for r in rows] == [b.id]
    seen_a = await c.get("/api/v1/audit-log?entity_type=risk", headers={H: str(a.id)})
    seen_b = await c.get("/api/v1/audit-log?entity_type=risk", headers={H: str(b.id)})
    assert seen_a.json()["total"] == 0 and seen_b.json()["total"] == 1


async def test_member_management_is_for_system_admins(
    session: AsyncSession, storage, two_projects
) -> None:
    a, _ = two_projects
    admin, _ = await client_as(storage, session, "root@example.test", "admin")
    director, user = await client_as(storage, session, "d@example.test", "director")
    url = f"/api/v1/projects/{a.id}/members/{user.id}"

    assert (await director.put(url, json={"role": "director"})).status_code == 403
    put = await admin.put(url, json={"role": "technical"})
    assert put.status_code == 200 and put.json()["role"] == "technical"
    assert (await admin.put(url, json={"role": "cost"})).json()["role"] == "cost"
    members = (await admin.get(f"/api/v1/projects/{a.id}/members")).json()
    assert [m["role"] for m in members if m["user_id"] == str(user.id)] == ["cost"]
    assert [p["code"] for p in (await director.get("/api/v1/projects")).json()] == ["A"]

    assert (await admin.delete(url)).status_code == 204
    assert (await admin.delete(url)).status_code == 404
    assert (await director.get("/api/v1/projects")).json() == []


async def test_a_new_user_is_seated_in_the_admins_current_project(
    session: AsyncSession, storage, two_projects
) -> None:
    _, b = two_projects
    admin, _ = await client_as(storage, session, "root@example.test", "admin")
    body = {"email": "new@example.test", "full_name": "Người mới", "role": "technical"}
    resp = await admin.post("/api/v1/users", json=body, headers={H: str(b.id)})
    assert resp.status_code == 201
    seats = (
        await session.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == uuid.UUID(resp.json()["id"])
            )
        )
    ).all()
    assert seats == [(b.id, "technical")]


async def test_the_alert_engine_keeps_projects_apart(session: AsyncSession, two_projects) -> None:
    from app.services.alert_engine import run_alerts

    a, b = two_projects
    await make_package(session, a)
    await make_package(session, b)
    await run_alerts(session)

    alerts = (await session.execute(select(Alert))).scalars().all()
    assert {x.project_id for x in alerts} <= {a.id, b.id}
    for alert in alerts:
        if alert.package_id is not None:
            package = await session.get(Package, alert.package_id)
            assert package is not None and package.project_id == alert.project_id


async def test_login_audit_rows_never_inherit_the_project_of_an_earlier_request(
    session: AsyncSession, storage, two_projects
) -> None:
    a, _ = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    body = {"title": "Rủi ro", "category": "supply", "probability": 3, "impact": 3}
    assert (await c.post("/api/v1/risks", json=body, headers={H: str(a.id)})).status_code == 201
    assert (await login(c, "d@example.test")).status_code == 200  # same connection, no project
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "login"))).scalars().all()
    )
    assert len(rows) == 2 and all(r.project_id is None for r in rows)


async def test_seeding_again_does_not_undo_a_removal(session: AsyncSession) -> None:
    from app.seed.project import seed_project

    kept = await make_user(session, "director", email="k@example.test", seat=False)
    removed = await make_user(session, "viewer", email="r@example.test", seat=False)
    project = await seed_project(session)  # a project nobody works on: both get a seat
    seats = lambda: select(ProjectMember.user_id).where(ProjectMember.project_id == project.id)  # noqa: E731
    assert set((await session.execute(seats())).scalars()) == {kept.id, removed.id}

    member = (
        await session.execute(select(ProjectMember).where(ProjectMember.user_id == removed.id))
    ).scalar_one()
    await session.delete(member)
    await session.commit()
    await seed_project(session)
    assert set((await session.execute(seats())).scalars()) == {kept.id}


async def test_api_answers_vary_by_project_so_caches_keep_projects_apart(
    session: AsyncSession, storage, two_projects
) -> None:
    a, _ = two_projects
    c, user = await client_as(storage, session, "d@example.test", "director")
    await seat(session, a, user, "director")
    resp = await c.get("/api/v1/packages", headers={H: str(a.id)})
    assert "x-project-id" in resp.headers["vary"].lower()
