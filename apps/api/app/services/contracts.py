"""Contract helpers shared by routers, seed and (later) the alert engine."""

from dataclasses import asdict
from datetime import date, timedelta

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, ContractParty, Organization, Package, Project
from app.schemas.contract import ContractOut, IssueOut, PartyOut
from app.services.rules import (
    ContractFacts,
    Issue,
    PackageFacts,
    PartyFacts,
    ProjectFacts,
    check_contract,
)

NON_NULLABLE = frozenset({"contract_no", "end_date_override", "price_adjustment", "status"})
# Consortium lead first, then sole contractor, then members (rows share one created_at).
PARTY_ORDER = case((ContractParty.role == "lead", 0), (ContractParty.role == "sole", 1), else_=2)


def computed_end(c: Contract) -> date | None:
    """SPEC 7.5 #9: end = start + duration - 1."""
    start = c.effective_date or c.signed_date
    if start and c.duration_days:
        return start + timedelta(days=c.duration_days - 1)
    return None


def apply_planned_end(c: Contract, sent: set[str]) -> None:
    """Fill/refresh `planned_end_date` unless the caller set it or chose to override."""
    if "planned_end_date" in sent or c.end_date_override:
        return
    end = computed_end(c)
    if end is not None:
        c.planned_end_date = end


async def contract_out(session: AsyncSession, contract: Contract) -> ContractOut:
    issues = await evaluate_contract(session, contract)
    rows = (
        await session.execute(
            select(ContractParty, Organization.name)
            .join(Organization, Organization.id == ContractParty.organization_id)
            .where(ContractParty.contract_id == contract.id)
            .order_by(PARTY_ORDER, Organization.name)
        )
    ).all()
    out = ContractOut.model_validate(contract)
    out.consistency = [IssueOut(**asdict(i)) for i in issues]
    out.needs_review = any(i.severity == "warning" for i in issues)
    out.parties = [
        PartyOut.model_validate(party).model_copy(update={"organization_name": name})
        for party, name in rows
    ]
    return out


def contract_facts(c: Contract) -> ContractFacts:
    return ContractFacts(
        value=c.value,
        duration_days=c.duration_days,
        signed_date=c.signed_date,
        effective_date=c.effective_date,
        planned_end_date=c.planned_end_date,
        end_date_override=c.end_date_override,
        contract_type=c.contract_type,
        price_adjustment=c.price_adjustment,
        advance_pct=c.advance_pct,
        advance_amount=c.advance_amount,
        performance_bond_pct=c.performance_bond_pct,
        performance_bond_amount=c.performance_bond_amount,
        warranty_bond_pct=c.warranty_bond_pct,
        warranty_bond_amount=c.warranty_bond_amount,
        investor_account=c.investor_account,
    )


async def evaluate_contract(session: AsyncSession, contract: Contract) -> list[Issue]:
    """Run the SPEC 7.5 consistency checks against the contract's current database state."""
    package = await session.get(Package, contract.package_id)
    assert package is not None
    project = await session.get(Project, package.project_id)
    assert project is not None
    parties = (
        (
            await session.execute(
                select(ContractParty).where(ContractParty.contract_id == contract.id)
            )
        )
        .scalars()
        .all()
    )
    return check_contract(
        contract_facts(contract),
        PackageFacts(package.winning_price, package.approved_duration_days),
        ProjectFacts(project.treasury_account),
        [PartyFacts(p.share_amount, p.advance_amount) for p in parties],
    )
