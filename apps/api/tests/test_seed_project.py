"""M2 acceptance: the seed shows all 8 packages and the 7.5 flags appear where SPEC 14 says."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, ContractParty, Organization, Package, Project
from app.seed.project import seed_project
from app.services.contracts import evaluate_contract

D = Decimal


@pytest.fixture
async def seeded(session: AsyncSession) -> dict[int, Package]:
    await seed_project(session)
    rows = (await session.execute(select(Package))).scalars().all()
    return {p.number: p for p in rows}


async def contract_of(session: AsyncSession, package: Package) -> Contract | None:
    return (
        await session.execute(select(Contract).where(Contract.package_id == package.id))
    ).scalar_one_or_none()


async def flags(session: AsyncSession, number: int, seeded: dict[int, Package]) -> dict[str, str]:
    contract = await contract_of(session, seeded[number])
    assert contract is not None
    return {i.code: i.severity for i in await evaluate_contract(session, contract)}


async def test_project_card(session: AsyncSession, seeded: dict[int, Package]) -> None:
    project = (await session.execute(select(Project))).scalar_one()
    assert project.total_investment == D(219_000_000_000)
    assert project.treasury_account == "9552.2.8200685"
    assert project.project_code_kbnn == "8200685"
    assert (project.start_year, project.end_year) == (2026, 2028)


async def test_eight_packages_with_prices(seeded: dict[int, Package]) -> None:
    assert sorted(seeded) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert {n: p.package_price for n, p in seeded.items()} == {
        1: D(237_382_337),
        2: D(270_141_231),
        3: D(117_472_203_146),
        4: D(62_298_200_000),
        5: D(14_946_900_000),
        6: D(1_820_685_517),
        7: D(509_634_139),
        8: D(720_713_320),
    }
    assert {n: p.winning_price for n, p in seeded.items()} == {
        1: D(237_382_337),
        2: None,
        3: None,
        4: D(51_505_400_000),
        5: D(13_599_975_000),
        6: D(1_726_920_000),
        7: None,
        8: None,
    }


async def test_unknown_values_stay_null_not_invented(
    session: AsyncSession, seeded: dict[int, Package]
) -> None:
    for number in (7, 8):
        contract = await contract_of(session, seeded[number])
        assert contract is not None and contract.value is None
    assert await contract_of(session, seeded[3]) is None


async def test_package_03_is_grey_with_reason(seeded: dict[int, Package]) -> None:
    p3 = seeded[3]
    assert p3.health == "grey" and p3.health_reason == "Chưa có hợp đồng"
    assert p3.etbmt_no == "IB2600424701"
    assert p3.status == "bidding" and p3.current_stage == "S2_SELECTION"


async def test_package_05_is_sensitive_only(seeded: dict[int, Package]) -> None:
    assert [n for n, p in seeded.items() if p.is_sensitive] == [5]


async def test_flags_appear_on_package_02_and_04(
    session: AsyncSession, seeded: dict[int, Package]
) -> None:
    f2 = await flags(session, 2, seeded)
    assert {
        "DURATION_NE_KHLCNT",
        "INVESTOR_ACCOUNT_NE_TREASURY",
        "LUMP_SUM_WITH_PRICE_ADJUSTMENT",
    } <= set(f2)
    assert await flags(session, 4, seeded) == {"END_DATE_MISMATCH": "warning"}


async def test_package_01_text_date_discrepancy_is_flagged(
    session: AsyncSession, seeded: dict[int, Package]
) -> None:
    # SPEC 14.3: text says 18/9, rule gives 17/9.
    assert await flags(session, 1, seeded) == {"END_DATE_MISMATCH": "warning"}


@pytest.mark.parametrize("number", [5, 7, 8])
async def test_clean_contracts_have_no_flags(
    number: int, session: AsyncSession, seeded: dict[int, Package]
) -> None:
    assert await flags(session, number, seeded) == {}


async def test_package_06_end_date_override_is_info_only(
    session: AsyncSession, seeded: dict[int, Package]
) -> None:
    assert await flags(session, 6, seeded) == {"END_DATE_MISMATCH": "info"}
    contract = await contract_of(session, seeded[6])
    assert contract is not None
    assert contract.advance_amount == D(518_076_000)
    assert (contract.penalty_rate_pct, contract.penalty_unit, contract.penalty_cap_pct) == (
        D(1),
        "day",
        D(8),
    )


async def test_consortium_shares(session: AsyncSession, seeded: dict[int, Package]) -> None:
    for number, expected in {
        4: [D(30_903_240_000), D(20_602_160_000)],
        5: [D(9_386_475_000), D(4_213_500_000)],
    }.items():
        contract = await contract_of(session, seeded[number])
        assert contract is not None
        parties = (
            (
                await session.execute(
                    select(ContractParty).where(ContractParty.contract_id == contract.id)
                )
            )
            .scalars()
            .all()
        )
        assert sorted((p.share_amount for p in parties), reverse=True) == expected
        assert {p.role for p in parties} == {"lead", "member"}


async def test_seed_is_idempotent(session: AsyncSession, seeded: dict[int, Package]) -> None:
    await seed_project(session)
    for model, expected in ((Package, 8), (Contract, 7), (ContractParty, 5), (Project, 1)):
        count = (await session.execute(select(func.count()).select_from(model))).scalar_one()
        assert count == expected
    orgs = (await session.execute(select(func.count()).select_from(Organization))).scalar_one()
    assert orgs >= 8
