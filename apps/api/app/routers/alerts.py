import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, select

from app.core.deps import MailerDep, SessionDep, require, require_roles
from app.core.errors import AppError
from app.core.rbac import Level
from app.core.scope import current_project_id
from app.models import Alert, Package, User
from app.schemas.alert import AlertAssign, AlertOut, AlertSnooze, RefreshOut
from app.schemas.common import Page, PaginationDep
from app.services import audit
from app.services.alert_jobs import refresh_alerts

router = APIRouter(tags=["alerts"])

Reader = Annotated[User, Depends(require("package", Level.READ))]
Writer = Annotated[User, Depends(require("risk", Level.WRITE))]
Operator = Annotated[User, Depends(require_roles("admin", "director"))]

_SEVERITY_ORDER = case((Alert.severity == "critical", 0), (Alert.severity == "warning", 1), else_=2)
_DEFAULT_STATUSES = ("open", "acknowledged")


def _out(alert: Alert, package_number: int | None) -> AlertOut:
    out = AlertOut.model_validate(alert)
    out.package_number = package_number
    out.can_snooze = alert.severity != "critical" and alert.status in _DEFAULT_STATUSES
    return out


async def _alert_or_404(session: SessionDep, alert_id: uuid.UUID) -> tuple[Alert, int | None]:
    row = (
        await session.execute(
            select(Alert, Package.number)
            .outerjoin(Package, Package.id == Alert.package_id)
            .where(Alert.id == alert_id, Alert.project_id == current_project_id())
        )
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Không tìm thấy cảnh báo")
    return row[0], row[1]


@router.get("/alerts", response_model=Page[AlertOut])
async def list_alerts(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    status: Annotated[
        str | None, Query(pattern="^(open|acknowledged|resolved|suppressed|active|all)$")
    ] = None,
    severity: Annotated[str | None, Query(pattern="^(info|warning|critical)$")] = None,
    alert_type: str | None = None,
    package_id: uuid.UUID | None = None,
    assigned_to: uuid.UUID | None = None,
) -> Page[AlertOut]:
    """Open and acknowledged alerts by default (`status=all` for history), critical first."""
    stmt = (
        select(Alert, Package.number)
        .outerjoin(Package, Package.id == Alert.package_id)
        .where(Alert.project_id == current_project_id())
    )
    if status in (None, "active"):
        stmt = stmt.where(Alert.status.in_(_DEFAULT_STATUSES))
    elif status != "all":
        stmt = stmt.where(Alert.status == status)
    for column, value in (
        (Alert.severity, severity),
        (Alert.alert_type, alert_type),
        (Alert.package_id, package_id),
        (Alert.assigned_to, assigned_to),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(
                _SEVERITY_ORDER, Alert.due_date.asc().nulls_last(), Alert.first_seen_at.desc()
            )
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).all()
    return Page[AlertOut](
        items=[_out(a, number) for a, number in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/alerts/refresh", response_model=RefreshOut)
async def refresh(_: Operator, mailer: MailerDep) -> RefreshOut:
    """Run the rule engine now instead of waiting for the next scheduled pass."""
    result, sent = await refresh_alerts(mailer)
    return RefreshOut(
        created=result.created,
        updated=result.updated,
        reopened=result.reopened,
        resolved=result.resolved,
        health_changed=result.health_changed,
        emails_sent=sent,
    )


@router.get("/alerts/{alert_id}", response_model=AlertOut)
async def get_alert(_: Reader, session: SessionDep, alert_id: uuid.UUID) -> AlertOut:
    alert, number = await _alert_or_404(session, alert_id)
    return _out(alert, number)


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
async def acknowledge(
    user: Writer, session: SessionDep, request: Request, alert_id: uuid.UUID
) -> AlertOut:
    alert, number = await _alert_or_404(session, alert_id)
    if alert.status == "resolved":
        raise AppError(409, "alert_resolved", "Cảnh báo đã tự đóng vì điều kiện không còn")
    before = alert.status
    alert.status = "acknowledged"
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(UTC)
    alert.snoozed_until = None
    alert.snooze_reason = None
    audit.record(
        session,
        action="update",
        entity_type="alert",
        entity_id=alert.id,
        user_id=user.id,
        changes={"status": {"before": before, "after": "acknowledged"}},
        request=request,
    )
    await session.commit()
    return _out(alert, number)


@router.post("/alerts/{alert_id}/snooze", response_model=AlertOut)
async def snooze(
    user: Writer, session: SessionDep, request: Request, alert_id: uuid.UUID, body: AlertSnooze
) -> AlertOut:
    """Hide a warning for up to 7 days with a reason; critical alerts cannot be snoozed."""
    alert, number = await _alert_or_404(session, alert_id)
    if alert.status == "resolved":
        raise AppError(409, "alert_resolved", "Cảnh báo đã tự đóng vì điều kiện không còn")
    if alert.severity == "critical":
        raise AppError(409, "critical_not_snoozable", "Cảnh báo nghiêm trọng không thể tạm hoãn")
    before = alert.status
    alert.status = "suppressed"
    alert.snoozed_until = datetime.now(UTC) + timedelta(days=body.days)
    alert.snooze_reason = body.reason
    audit.record(
        session,
        action="update",
        entity_type="alert",
        entity_id=alert.id,
        user_id=user.id,
        changes={
            "status": {"before": before, "after": "suppressed"},
            "snooze_reason": {"before": None, "after": body.reason},
        },
        request=request,
    )
    await session.commit()
    return _out(alert, number)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
async def assign(
    user: Writer, session: SessionDep, request: Request, alert_id: uuid.UUID, body: AlertAssign
) -> AlertOut:
    alert, number = await _alert_or_404(session, alert_id)
    if body.assigned_to is not None:
        assignee = await session.get(User, body.assigned_to)
        if assignee is None or not assignee.is_active:
            raise AppError(422, "validation_error", "Người xử lý không hợp lệ", ["assigned_to"])
    before = alert.assigned_to
    alert.assigned_to = body.assigned_to
    audit.record(
        session,
        action="update",
        entity_type="alert",
        entity_id=alert.id,
        user_id=user.id,
        changes={"assigned_to": {"before": before, "after": body.assigned_to}},
        request=request,
    )
    await session.commit()
    return _out(alert, number)
