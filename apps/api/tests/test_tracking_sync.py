import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, Package, Risk, Task, User
from app.seed.project import seed_project
from app.services.tracking_details import read_detail_sheets
from app.services.tracking_sync import SyncReport, run_sync
from app.services.tracking_workbook import read_tracking_workbook
from tests.conftest import make_user

WORKBOOK = (
    Path(__file__).resolve().parents[3] / "docs" / "Tracking_Cac_Goi_Thau_DA_Cap_Xa_Lam_Dong.xlsx"
)
EXEC_AND_CBDT_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 101, 102, 103]
ACTOR_EMAIL = "sync-admin@example.test"


async def _sync(session: AsyncSession, path: Path, apply: bool) -> SyncReport:
    actor = (
        await session.execute(select(User).where(User.email == ACTOR_EMAIL))
    ).scalar_one_or_none() or await make_user(session, "admin", email=ACTOR_EMAIL)
    return await run_sync(
        session, read_tracking_workbook(path), read_detail_sheets(path), actor, apply
    )


async def _package_numbers(session: AsyncSession) -> list[int]:
    numbers = (await session.execute(select(Package.number).order_by(Package.number))).scalars()
    return list(numbers)


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    await seed_project(session)


async def test_first_sync_creates_eleven_packages_with_their_milestones_and_risks(
    session: AsyncSession, seeded: None
) -> None:
    report = await _sync(session, WORKBOOK, apply=True)

    assert report.applied
    assert not any(f.severity == "error" for f in report.findings)
    assert await _package_numbers(session) == EXEC_AND_CBDT_NUMBERS
    assert await session.scalar(select(func.count()).select_from(Task)) == 40
    assert (
        await session.scalar(
            select(func.count()).select_from(Risk).where(Risk.source == "workbook")
        )
        == 14
    )


async def test_second_sync_of_the_same_file_changes_nothing(
    session: AsyncSession, seeded: None
) -> None:
    await _sync(session, WORKBOOK, apply=True)

    again = await _sync(session, WORKBOOK, apply=True)

    assert again.changes and all(change.action == "unchanged" for change in again.changes)


async def test_dry_run_writes_nothing(session: AsyncSession, seeded: None) -> None:
    before = await _package_numbers(session)

    report = await _sync(session, WORKBOOK, apply=False)

    assert not report.applied
    assert report.changes
    assert await _package_numbers(session) == before


async def test_seeded_preparation_packages_move_to_their_cbdt_numbers(
    session: AsyncSession, seeded: None
) -> None:
    await _sync(session, WORKBOOK, apply=True)

    cbdt_03 = (await session.execute(select(Package).where(Package.number == 103))).scalar_one()
    contract = (
        await session.execute(select(Contract).where(Contract.package_id == cbdt_03.id))
    ).scalar_one()
    assert contract.contract_no.startswith("41/2026")
    assert cbdt_03.winning_org_text == "Công ty TNHH Thẩm định giá và Đo đạc Địa chính BTA Việt Nam"


async def test_package_03_is_tb_cntt_without_a_contract(
    session: AsyncSession, seeded: None
) -> None:
    await _sync(session, WORKBOOK, apply=True)

    package_03 = (await session.execute(select(Package).where(Package.number == 3))).scalar_one()
    assert package_03.package_price == 117_472_203_146
    contracts = (
        await session.execute(select(Contract).where(Contract.package_id == package_03.id))
    ).scalars()
    assert list(contracts) == []


async def test_a_changed_price_in_the_workbook_is_written_to_the_database(
    session: AsyncSession, seeded: None, tmp_path: Path
) -> None:
    copied = tmp_path / "tracking.xlsx"
    shutil.copy(WORKBOOK, copied)
    book = load_workbook(copied)
    book["00_TONG_HOP"]["D16"].value = 237_382_338
    book.save(copied)

    await _sync(session, copied, apply=True)

    package_01 = (await session.execute(select(Package).where(Package.number == 1))).scalar_one()
    assert package_01.package_price == 237_382_338


async def test_unsigned_package_drops_a_winner_left_from_an_older_row(
    session: AsyncSession, seeded: None
) -> None:
    await _sync(session, WORKBOOK, apply=True)
    package_03 = (await session.execute(select(Package).where(Package.number == 3))).scalar_one()
    package_03.winning_price = 430_000_000
    package_03.winning_org_text = "Công ty TNHH Thẩm định giá và Đo đạc Địa chính BTA Việt Nam"
    await session.commit()

    report = await _sync(session, WORKBOOK, apply=True)

    assert report.applied, report.findings
    await session.refresh(package_03)
    assert package_03.winning_price is None
    assert package_03.winning_org_text is None
    assert any(c.entity == "package" and "winning_price" in c.fields for c in report.changes)


async def test_contract_the_workbook_does_not_list_blocks_the_write(
    session: AsyncSession, seeded: None
) -> None:
    await _sync(session, WORKBOOK, apply=True)
    package_03 = (await session.execute(select(Package).where(Package.number == 3))).scalar_one()
    session.add(Contract(package_id=package_03.id, contract_no="STRAY"))
    await session.commit()

    report = await _sync(session, WORKBOOK, apply=True)

    assert not report.applied
    assert any(f.code == "contract_not_in_workbook" for f in report.findings)
