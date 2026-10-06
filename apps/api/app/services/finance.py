"""Guarantee/payment helpers shared by routers, seed and (M7) the alert engine."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Contract, Guarantee, Payment
from app.services.guarantee_rules import (
    ContractTimeline,
    Finding,
    GuaranteeFacts,
    check_guarantees,
    guarantee_status,
)

# Payment workflow: who may move a payment where. `paid` is reached only through mark-paid.
PAYMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"requested"}),
    "requested": frozenset({"approved", "rejected", "planned"}),
    "approved": frozenset({"rejected"}),
    "rejected": frozenset({"planned"}),
    "paid": frozenset(),
}
APPROVAL_TARGETS = frozenset({"approved", "rejected"})


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().app_timezone)).date()


def days_left(expiry: date | None, today: date) -> int | None:
    return None if expiry is None else (expiry - today).days


def effective_status(g: Guarantee, today: date) -> str:
    return guarantee_status(g.status, g.expiry_date, today)


def guarantee_facts(g: Guarantee) -> GuaranteeFacts:
    return GuaranteeFacts(
        id=str(g.id),
        guarantee_type=g.guarantee_type,
        status=g.status,
        expiry_date=g.expiry_date,
        required=g.required,
    )


async def recovered_advance(session: AsyncSession, contract_id: object) -> Decimal:
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.contract_id == contract_id,
                Payment.payment_type == "recovery",
                Payment.status == "paid",
            )
        )
    ).scalar_one()
    return Decimal(total)


async def contract_timeline(session: AsyncSession, contract: Contract) -> ContractTimeline:
    return ContractTimeline(
        start=contract.effective_date or contract.signed_date,
        end=contract.extended_end_date or contract.planned_end_date,
        advance_amount=contract.advance_amount,
        recovered_amount=await recovered_advance(session, contract.id),
    )


async def guarantee_findings(
    session: AsyncSession,
    contract: Contract,
    guarantees: list[Guarantee],
    today: date,
) -> list[Finding]:
    term = contract.payment_term_days
    kwargs = {"payment_term_days": term} if term is not None else {}
    return check_guarantees(
        await contract_timeline(session, contract),
        [guarantee_facts(g) for g in guarantees],
        today,
        **kwargs,
    )
