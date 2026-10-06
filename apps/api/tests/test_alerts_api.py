"""M7: alert centre API, e-mail notifications and the write hook (SPEC 4.10, 7.1)."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.main import create_app
from app.models import Alert, AuditLog
from app.seed.checklists import seed_checklists
from app.seed.finance import seed_finance
from app.seed.progress import seed_progress
from app.seed.project import seed_project
from app.seed.risks import seed_risks
from app.services.alert_engine import run_alerts
from app.services.mailer import MemoryMailer
from app.services.notify import send_critical_notifications, send_daily_digest
from tests.conftest import ALL_ROLES, PASSWORD, login, make_user

NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
GHOST = "00000000-0000-0000-0000-000000000000"
WRITERS = {"admin", "director", "procurement", "technical", "cost", "onsite"}


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    await seed_project(session)
    await seed_finance(session)
    await seed_checklists(session)
    await seed_progress(session)
    await seed_risks(session)
    await run_alerts(session, NOW)


async def first(session: AsyncSession, severity: str, alert_type: str | None = None) -> Alert:
    stmt = select(Alert).where(Alert.severity == severity, Alert.status == "open")
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    row = (await session.execute(stmt.order_by(Alert.fingerprint))).scalars().first()
    assert row is not None
    return row


# --- list --------------------------------------------------------------------------------------


async def test_list_puts_critical_first_and_includes_package_number(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    data = (await c.get("/api/v1/alerts", params={"page_size": 100})).json()
    rank = {"critical": 0, "warning": 1, "info": 2}
    ranks = [rank[a["severity"]] for a in data["items"]]
    assert ranks == sorted(ranks) and ranks[0] == 0
    assert data["total"] == len(data["items"]) > 0
    five = [a for a in data["items"] if a["alert_type"] == "ADVANCE_GUARANTEE_SHORT"]
    assert five and all(a["package_number"] == 5 and a["can_snooze"] is False for a in five)


async def test_list_filters_and_default_hides_resolved(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "viewer")
    crit = (await c.get("/api/v1/alerts", params={"severity": "critical", "page_size": 100})).json()
    assert crit["items"] and {a["severity"] for a in crit["items"]} == {"critical"}
    typed = (await c.get("/api/v1/alerts", params={"alert_type": "GUARANTEE_MISSING"})).json()
    assert {a["alert_type"] for a in typed["items"]} == {"GUARANTEE_MISSING"}
    assert (await c.get("/api/v1/alerts", params={"status": "bogus"})).status_code == 422

    row = await first(session, "warning")
    row.status = "resolved"
    await session.commit()
    page = (await c.get("/api/v1/alerts", params={"page_size": 100})).json()
    assert str(row.id) not in {a["id"] for a in page["items"]}
    history = (await c.get("/api/v1/alerts", params={"status": "all", "page_size": 100})).json()
    assert str(row.id) in {a["id"] for a in history["items"]}


async def test_unauthenticated_and_unknown_alert(
    session: AsyncSession, seeded: None, client, make_client_for
) -> None:
    assert (await client.get("/api/v1/alerts")).status_code == 401
    c = await make_client_for(session, "viewer")
    assert (await c.get(f"/api/v1/alerts/{GHOST}")).status_code == 404


# --- ack / snooze / assign ---------------------------------------------------------------------


async def test_ack_and_assign_are_audited(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "technical")
    alert = await first(session, "warning")
    r = await c.post(f"/api/v1/alerts/{alert.id}/ack")
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged" and r.json()["acknowledged_by"]

    me = (await c.get("/api/v1/auth/me")).json()
    r = await c.patch(f"/api/v1/alerts/{alert.id}", json={"assigned_to": me["id"]})
    assert r.status_code == 200 and r.json()["assigned_to"] == me["id"]
    r = await c.patch(f"/api/v1/alerts/{alert.id}", json={"assigned_to": GHOST})
    assert r.status_code == 422
    r = await c.patch(f"/api/v1/alerts/{alert.id}", json={"assigned_to": None})
    assert r.json()["assigned_to"] is None

    audits = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_id == str(alert.id))))
        .scalars()
        .all()
    )
    assert len(audits) == 3 and {a.entity_type for a in audits} == {"alert"}


async def test_snooze_rules(session: AsyncSession, seeded: None, make_client_for) -> None:
    c = await make_client_for(session, "director")
    warn = await first(session, "warning")
    crit = await first(session, "critical")

    ok = await c.post(
        f"/api/v1/alerts/{warn.id}/snooze", json={"days": 7, "reason": "Chờ phản hồi"}
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "suppressed" and body["snooze_reason"] == "Chờ phản hồi"
    assert body["snoozed_until"] and body["can_snooze"] is False

    r = await c.post(f"/api/v1/alerts/{crit.id}/snooze", json={"days": 1, "reason": "x"})
    assert (r.status_code, r.json()["error"]["code"]) == (409, "critical_not_snoozable")
    other = await first(session, "warning")
    for bad in ({"days": 8, "reason": "x"}, {"days": 0, "reason": "x"}, {"days": 2, "reason": " "}):
        assert (await c.post(f"/api/v1/alerts/{other.id}/snooze", json=bad)).status_code == 422


async def test_resolved_alert_cannot_be_acknowledged_or_snoozed(
    session: AsyncSession, seeded: None, make_client_for
) -> None:
    c = await make_client_for(session, "director")
    alert = await first(session, "warning")
    alert.status = "resolved"
    await session.commit()
    r = await c.post(f"/api/v1/alerts/{alert.id}/ack")
    assert (r.status_code, r.json()["error"]["code"]) == (409, "alert_resolved")
    r = await c.post(f"/api/v1/alerts/{alert.id}/snooze", json={"days": 1, "reason": "x"})
    assert r.status_code == 409


async def test_role_matrix(session: AsyncSession, seeded: None, make_client_for) -> None:
    # refresh runs on the real date and may close date-driven warnings: use a stable alert
    alert = await first(session, "critical", "ADVANCE_GUARANTEE_SHORT")
    for role in ALL_ROLES:
        c = await make_client_for(session, role)
        assert (await c.get("/api/v1/alerts")).status_code == 200
        expected = 200 if role in WRITERS else 403
        assert (await c.post(f"/api/v1/alerts/{alert.id}/ack")).status_code == expected, role
        refresh = (await c.post("/api/v1/alerts/refresh")).status_code
        assert refresh == (200 if role in {"admin", "director"} else 403), role


# --- refresh and e-mail ------------------------------------------------------------------------


async def test_refresh_runs_the_engine_and_emails_new_critical_alerts_once(
    session: AsyncSession, make_client_for
) -> None:
    await seed_project(session)
    await seed_finance(session)
    await seed_checklists(session)
    await seed_progress(session)
    mailer = MemoryMailer()
    c = await make_client_for(session, "director")
    c._transport.app.state.mailer = mailer  # type: ignore[attr-defined]

    first_run = (await c.post("/api/v1/alerts/refresh")).json()
    assert first_run["created"] > 0 and first_run["emails_sent"] == 1
    (mail,) = mailer.sent
    assert mail.to == "director@example.test" and "nghiêm trọng" in mail.subject
    assert "Gói 05" in mail.text and "/alerts" in mail.text

    second = (await c.post("/api/v1/alerts/refresh")).json()
    assert (second["created"], second["resolved"], second["emails_sent"]) == (0, 0, 0)
    assert len(mailer.sent) == 1  # critical alerts are mailed once, not on every run


async def test_critical_mail_goes_to_directors_and_the_assignee(
    session: AsyncSession, seeded: None
) -> None:
    await make_user(session, "director")
    tech = await make_user(session, "technical")
    crit = await first(session, "critical")
    crit.assigned_to = tech.id
    await session.commit()

    mailer = MemoryMailer()
    sent = await send_critical_notifications(session, mailer)
    by_to = {m.to: m for m in mailer.sent}
    assert sent == len(mailer.sent) == 2
    assert set(by_to) == {"director@example.test", "technical@example.test"}
    # the assignee only hears about their own alert, the director about all of them
    assert by_to["technical@example.test"].text.count("[Nghiêm trọng]") == 1
    assert by_to["director@example.test"].text.count("[Nghiêm trọng]") > 1


async def test_refused_recipient_is_retried_next_time(session: AsyncSession, seeded: None) -> None:
    await make_user(session, "director")
    mailer = MemoryMailer(fail_for={"director@example.test"})
    assert await send_critical_notifications(session, mailer) == 0
    pending = (
        (
            await session.execute(
                select(Alert).where(
                    Alert.severity == "critical",
                    Alert.status == "open",
                    Alert.notified_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert pending  # nothing was marked as sent

    mailer.fail_for.clear()
    assert await send_critical_notifications(session, mailer) == 1
    left = await session.execute(
        select(Alert.id).where(
            Alert.severity == "critical", Alert.status == "open", Alert.notified_at.is_(None)
        )
    )
    assert left.first() is None


async def test_inactive_assignee_gets_no_mail(session: AsyncSession, seeded: None) -> None:
    gone = await make_user(session, "technical", is_active=False)
    crit = await first(session, "critical")
    crit.assigned_to = gone.id
    await session.commit()
    mailer = MemoryMailer()
    await send_critical_notifications(session, mailer)  # no directors, no active assignee
    assert mailer.sent == []


async def test_daily_digest_summarises_open_alerts_per_recipient(
    session: AsyncSession, seeded: None
) -> None:
    director = await make_user(session, "director")
    tech = await make_user(session, "technical")
    warn = await first(session, "warning")
    warn.assigned_to = tech.id
    await session.commit()

    mailer = MemoryMailer()
    assert await send_daily_digest(session, mailer) == 2
    by_to = {m.to: m for m in mailer.sent}
    assert director.email in by_to and "Tóm tắt cảnh báo" in by_to[director.email].subject
    assert by_to[tech.email].text.count("- [") == 1

    empty = MemoryMailer()
    await session.execute(Alert.__table__.delete())
    await session.commit()
    assert await send_daily_digest(session, empty) == 0 and empty.sent == []


# --- write hook --------------------------------------------------------------------------------


async def _authed(app, email: str) -> httpx.AsyncClient:
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    resp = await login(c, email, PASSWORD)
    c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
    return c


async def test_a_write_triggers_an_engine_pass(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_project(session)
    await seed_finance(session)
    await make_user(session, "director")
    monkeypatch.setenv("ALERT_REFRESH_ON_WRITE", "true")
    get_settings.cache_clear()
    try:
        app = create_app(mailer=MemoryMailer())
        c = await _authed(app, "director@example.test")
        try:
            assert (await c.get("/api/v1/alerts")).json()["total"] == 0  # reads never trigger

            created = await c.post(
                "/api/v1/risks",
                json={"title": "Rủi ro mới", "category": "schedule", "probability": 3, "impact": 3},
            )
            assert created.status_code == 201
            await app.state.write_refresh.drain()
            assert (await c.get("/api/v1/alerts")).json()["total"] > 0
            assert len(app.state.mailer.sent) == 1
        finally:
            await c.aclose()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


async def test_failed_requests_do_not_trigger(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_project(session)
    await make_user(session, "director")
    monkeypatch.setenv("ALERT_REFRESH_ON_WRITE", "true")
    get_settings.cache_clear()
    try:
        app = create_app(mailer=MemoryMailer())
        c = await _authed(app, "director@example.test")
        try:
            assert (await c.post("/api/v1/risks", json={"title": ""})).status_code == 422
            await app.state.write_refresh.drain()
            assert (await c.get("/api/v1/alerts")).json()["total"] == 0
        finally:
            await c.aclose()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
