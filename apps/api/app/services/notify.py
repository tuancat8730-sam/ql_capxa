"""Alert e-mails (SPEC 4.10): critical alerts go out at once, a digest at 08:00 Vietnam time.

Recipients are the assignee of an alert and every active director.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Alert, ProjectMember, User
from app.services.mailer import Email, Mailer

logger = logging.getLogger("qlda.notify")

SEVERITY_LABEL = {"critical": "Nghiêm trọng", "warning": "Cảnh báo", "info": "Thông tin"}
_RANK = {"critical": 0, "warning": 1, "info": 2}


async def _directors(
    session: AsyncSession, project_ids: set[uuid.UUID]
) -> list[tuple[User, uuid.UUID]]:
    """Active directors of the given projects, as (user, project id) pairs."""
    rows = await session.execute(
        select(User, ProjectMember.project_id)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(
            ProjectMember.role == "director",
            ProjectMember.project_id.in_(project_ids),
            User.is_active.is_(True),
        )
        .order_by(User.email)
    )
    return [(u, pid) for u, pid in rows.all()]


async def _recipients_for(
    session: AsyncSession, alerts: list[Alert]
) -> dict[str, tuple[User, list[Alert]]]:
    """email -> (user, alerts they should hear about).

    Directors hear about every alert of their projects, assignees about their own.
    """
    by_email: dict[str, tuple[User, list[Alert]]] = {}
    for director, project_id in await _directors(session, {a.project_id for a in alerts}):
        mine = [a for a in alerts if a.project_id == project_id]
        if director.email in by_email:
            by_email[director.email][1].extend(
                a for a in mine if a not in by_email[director.email][1]
            )
        else:
            by_email[director.email] = (director, mine)
    assignee_ids = {a.assigned_to for a in alerts if a.assigned_to}
    if assignee_ids:
        users = (await session.execute(select(User).where(User.id.in_(assignee_ids)))).scalars()
        for user in users:
            if not user.is_active or user.email in by_email:
                continue
            mine = [a for a in alerts if a.assigned_to == user.id]
            by_email[user.email] = (user, mine)
    return by_email


def _line(alert: Alert) -> str:
    due = f" (hạn {alert.due_date:%d/%m/%Y})" if alert.due_date else ""
    return f"- [{SEVERITY_LABEL[alert.severity]}] {alert.title}: {alert.message}{due}"


def _body(name: str, intro: str, alerts: list[Alert]) -> str:
    base = get_settings().app_base_url.rstrip("/")
    lines = [f"Chào {name},", "", intro, ""]
    lines += [_line(a) for a in sorted(alerts, key=lambda a: (_RANK[a.severity], a.title))]
    lines += ["", f"Xem chi tiết: {base}/alerts"]
    return "\n".join(lines)


async def send_critical_notifications(
    session: AsyncSession, mailer: Mailer, now: datetime | None = None
) -> int:
    """E-mail every open critical alert once (SPEC 4.10); returns the number of e-mails sent.

    An alert is marked `notified_at` only when all its recipients got the mail, so a refused
    recipient is retried on the next run.
    """
    now = now or datetime.now(UTC)
    pending = list(
        (
            await session.execute(
                select(Alert).where(
                    Alert.status == "open",
                    Alert.severity == "critical",
                    Alert.notified_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not pending:
        return 0
    recipients = await _recipients_for(session, pending)
    failed: set[str] = set()
    sent = 0
    for email, (user, items) in recipients.items():
        if not items:
            continue
        subject = f"[QLDA] {len(items)} cảnh báo nghiêm trọng mới"
        try:
            await mailer.send(
                Email(email, subject, _body(user.full_name, "Có cảnh báo nghiêm trọng mới:", items))
            )
            sent += 1
        except Exception:
            logger.exception("critical alert e-mail to %s failed", email)
            failed.add(email)
    for alert in pending:
        owners = [e for e, (_, items) in recipients.items() if alert in items]
        # no recipient at all (no director yet): mark it so it is not retried forever
        if not failed.intersection(owners):
            alert.notified_at = now
    await session.commit()
    return sent


async def send_daily_digest(session: AsyncSession, mailer: Mailer) -> int:
    """Morning summary of open warning/critical alerts; returns the number of e-mails sent."""
    open_alerts = list(
        (
            await session.execute(
                select(Alert).where(
                    Alert.status.in_(("open", "acknowledged")),
                    Alert.severity.in_(("critical", "warning")),
                )
            )
        )
        .scalars()
        .all()
    )
    if not open_alerts:
        return 0
    recipients = await _recipients_for(session, open_alerts)
    sent = 0
    for email, (user, items) in recipients.items():
        if not items:
            continue
        crit = sum(1 for a in items if a.severity == "critical")
        subject = f"[QLDA] Tóm tắt cảnh báo: {crit} nghiêm trọng, {len(items) - crit} cần chú ý"
        try:
            await mailer.send(
                Email(email, subject, _body(user.full_name, "Cảnh báo đang mở hôm nay:", items))
            )
            sent += 1
        except Exception:
            logger.exception("digest e-mail to %s failed", email)
    return sent
