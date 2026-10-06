"""Seed for the Lam Dong commune equipment project (SPEC section 14).

Only facts stated in SPEC 14 are stored. Anything the spec marks null / "chua ro" stays NULL
and is listed in docs/OPEN_QUESTIONS.md. All writes are get-or-create, so reruns change nothing.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, ContractParty, Organization, Package, Project

D = Decimal

INVESTOR = "Sở Khoa học và Công nghệ tỉnh Lâm Đồng"
CONTRACTORS = {
    "An Lập Thịnh": "contractor",
    "Trường Thịnh NT": "contractor",
    "Nguyên Luân": "contractor",
    "TTB Mẫu Giáo Ti Ti": "contractor",
    "P&N": "contractor",
    "BSN": "contractor",
    "Sài Gòn Mới": "consultant",
}

PROJECT: dict[str, Any] = {
    "code": "8200685",
    "name": (
        "Đầu tư trang thiết bị phục vụ hoạt động của chính quyền cấp xã và triển khai "
        "Đề án 06 trên địa bàn tỉnh Lâm Đồng"
    ),
    "total_investment": D(219_000_000_000),
    "funding_source": "Ngân sách tỉnh",
    "start_year": 2026,
    "end_year": 2028,
    "location": "Tỉnh Lâm Đồng",
    "treasury_account": "9552.2.8200685",
    "project_code_kbnn": "8200685",
    "description": "Quyết định: 2824, 3255, 220, 239 (KHLCNT).",
}


@dataclass(frozen=True)
class PartySeed:
    org: str
    role: str
    share_pct: Decimal | None = None
    share_amount: Decimal | None = None


@dataclass(frozen=True)
class ContractSeed:
    contract_no: str
    fields: dict[str, Any]
    parties: tuple[PartySeed, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PackageSeed:
    number: int
    price: Decimal
    package_type: str
    fields: dict[str, Any]
    contract: ContractSeed | None = None


_SIGNED = {"status": "contract_signed", "current_stage": "S3_EXECUTION"}

PACKAGES: tuple[PackageSeed, ...] = (
    PackageSeed(
        1,
        D(237_382_337),
        "goods",
        {**_SIGNED, "winning_price": D(237_382_337), "winning_org_text": "An Lập Thịnh"},
        ContractSeed(
            "53",
            {
                "signed_date": date(2026, 7, 20),
                "duration_days": 60,
                "planned_end_date": date(2026, 9, 18),
                "value": D(237_382_337),
                "data_quality_note": "Văn bản ghi kết thúc 18/9; tính theo quy tắc là 17/9.",
            },
        ),
    ),
    PackageSeed(
        2,
        D(270_141_231),
        "goods",
        {
            **_SIGNED,
            "approved_duration_days": 60,
            "winning_org_text": "Trường Thịnh NT",
            "notes": "Giá trúng thầu theo HĐ 54 (chưa có giá trị hợp đồng).",
        },
        ContractSeed(
            "54",
            {
                "duration_days": 90,
                "planned_end_date": date(2026, 9, 18),
                "contract_type": "lump_sum",
                "price_adjustment": True,
                "investor_account": "9552.2.8171939",
                "penalty_rate_pct": D(10),
                "penalty_unit": "week",
                "penalty_cap_pct": D(20),
                "data_quality_note": (
                    "Điều khoản sai khác: thiết kế thi công, điều chỉnh giá so với trọn gói, "
                    "90 so với 60 ngày, tài khoản khác 8200685, phạt 10%/tuần tối đa 20%."
                ),
            },
        ),
    ),
    PackageSeed(
        3,
        D(117_472_203_146),
        "goods",
        {
            "status": "bidding",
            "current_stage": "S2_SELECTION",
            "etbmt_no": "IB2600424701",
            "health": "grey",
            "health_reason": "Chưa có hợp đồng",
            "notes": (
                "E-TBMT IB2600424701; Viettel E-HSDT 101.886.000.000; "
                "BĐDT 3.524.166.000; chưa có hợp đồng."
            ),
        },
    ),
    PackageSeed(
        4,
        D(62_298_200_000),
        "goods",
        {
            **_SIGNED,
            "winning_price": D(51_505_400_000),
            "winning_org_text": "Liên danh Nguyên Luân (60%) – TTB Mẫu Giáo Ti Ti (40%)",
            "notes": "Giá trúng thầu thấp hơn giá gói thầu 17,3%.",
        },
        ContractSeed(
            "71",
            {
                "signed_date": date(2026, 9, 14),
                "duration_days": 60,
                "planned_end_date": date(2026, 11, 13),
                "value": D(51_505_400_000),
                "advance_pct": D(30),
                "advance_amount": D(15_451_620_000),
                "performance_bond_pct": D(3),
                "performance_bond_amount": D(1_545_162_000),
                "data_quality_note": "Văn bản ghi kết thúc 13/11; tính theo quy tắc là 12/11.",
            },
            (
                PartySeed("Nguyên Luân", "lead", D(60), D(30_903_240_000)),
                PartySeed("TTB Mẫu Giáo Ti Ti", "member", D(40), D(20_602_160_000)),
            ),
        ),
    ),
    PackageSeed(
        5,
        D(14_946_900_000),
        "goods",
        {
            **_SIGNED,
            "is_sensitive": True,
            "winning_price": D(13_599_975_000),
            "winning_org_text": "Liên danh P&N – BSN",
        },
        ContractSeed(
            "72",
            {
                "signed_date": date(2026, 9, 14),
                "duration_days": 60,
                "planned_end_date": date(2026, 11, 12),
                "value": D(13_599_975_000),
                "advance_pct": D(30),
                "advance_amount": D(4_079_992_500),
                "performance_bond_pct": D(3),
                "performance_bond_amount": D(407_999_250),
                "data_quality_note": (
                    "Tạm ứng suy ra từ tổng hai bảo lãnh tạm ứng (TPBank, BIDV) [OCR]; "
                    "vai trò đứng đầu liên danh chưa xác nhận."
                ),
            },
            (
                PartySeed("P&N", "lead", None, D(9_386_475_000)),
                PartySeed("BSN", "member", None, D(4_213_500_000)),
            ),
        ),
    ),
    PackageSeed(
        6,
        D(1_820_685_517),
        "consulting",
        {
            **_SIGNED,
            "winning_price": D(1_726_920_000),
            "winning_org_text": "Sài Gòn Mới",
            "consulting_role": "tvqlda",
        },
        ContractSeed(
            "80",
            {
                "signed_date": date(2026, 9, 24),
                "duration_days": 120,
                "planned_end_date": date(2027, 1, 22),
                "end_date_override": True,
                "value": D(1_726_920_000),
                "advance_pct": D(30),
                "advance_amount": D(518_076_000),
                "penalty_rate_pct": D(1),
                "penalty_unit": "day",
                "penalty_cap_pct": D(8),
                "data_quality_note": (
                    "Văn bản ghi kết thúc 22/01/2027; ngày hiệu lực (24/9 hay 25/9) chưa rõ."
                ),
            },
            (PartySeed("Sài Gòn Mới", "sole"),),
        ),
    ),
    PackageSeed(
        7,
        D(509_634_139),
        "consulting",
        {**_SIGNED, "consulting_role": "tvgs"},
        ContractSeed(
            "73",
            {
                # SPEC 14.6 (9): the supervision contract ends about 13/12/2026, ahead of the
                # supply packages. The exact date is still to be confirmed (OPEN_QUESTIONS).
                "planned_end_date": date(2026, 12, 13),
                "data_quality_note": "Ngày kết thúc ước tính ~13/12/2026 (SPEC 14.6).",
            },
        ),
    ),
    PackageSeed(
        8,
        D(720_713_320),
        "consulting",
        {**_SIGNED, "consulting_role": "other"},
        ContractSeed("74", {}),
    ),
)


async def _org(session: AsyncSession, name: str, org_type: str) -> Organization:
    org = (
        await session.execute(select(Organization).where(Organization.name == name))
    ).scalar_one_or_none()
    if org is None:
        org = Organization(name=name, short_name=name, org_type=org_type)
        session.add(org)
        await session.flush()
    return org


def _backfill(obj: Package | Contract, fields: dict[str, Any]) -> None:
    """Fill columns added after the first seed; values someone already entered are kept."""
    for key, value in fields.items():
        if getattr(obj, key) is None:
            setattr(obj, key, value)


async def seed_project(session: AsyncSession) -> Project:
    investor = await _org(session, INVESTOR, "investor")
    orgs = {name: await _org(session, name, kind) for name, kind in CONTRACTORS.items()}

    project = (
        await session.execute(select(Project).where(Project.code == PROJECT["code"]))
    ).scalar_one_or_none()
    if project is None:
        project = Project(investor_org_id=investor.id, **PROJECT)
        session.add(project)
        await session.flush()

    for seed in PACKAGES:
        package = (
            await session.execute(
                select(Package).where(
                    Package.project_id == project.id, Package.number == seed.number
                )
            )
        ).scalar_one_or_none()
        if package is None:
            package = Package(
                project_id=project.id,
                number=seed.number,
                name=f"Gói thầu số {seed.number:02d}",
                package_price=seed.price,
                package_type=seed.package_type,
                **seed.fields,
            )
            session.add(package)
            await session.flush()
        else:
            _backfill(package, seed.fields)
        if seed.contract is None:
            continue
        contract = (
            await session.execute(select(Contract).where(Contract.package_id == package.id))
        ).scalar_one_or_none()
        if contract is None:
            contract = Contract(
                package_id=package.id, contract_no=seed.contract.contract_no, **seed.contract.fields
            )
            session.add(contract)
            await session.flush()
            for party in seed.contract.parties:
                session.add(
                    ContractParty(
                        contract_id=contract.id,
                        organization_id=orgs[party.org].id,
                        role=party.role,
                        share_pct=party.share_pct,
                        share_amount=party.share_amount,
                    )
                )
        else:
            _backfill(contract, seed.contract.fields)
    await session.commit()
    return project
