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

from app.models import (
    Contract,
    ContractParty,
    Organization,
    Package,
    Project,
    ProjectMember,
    User,
)

D = Decimal

BTA = "Công ty TNHH Thẩm định giá và Đo đạc Địa chính BTA Việt Nam"

INVESTOR = "Sở Khoa học và Công nghệ tỉnh Lâm Đồng"
CONTRACTORS = {
    "An Lập Thịnh": "contractor",
    "Trường Thịnh NT": "contractor",
    "Nguyên Luân": "contractor",
    "TTB Mẫu Giáo Ti Ti": "contractor",
    "P&N": "contractor",
    "BSN": "contractor",
    "Sài Gòn Mới": "consultant",
    "Công ty Cổ phần Tư vấn Quang Trung": "consultant",
    "Công ty TNHH Hưng Dũng Lâm Đồng": "consultant",
    BTA: "consultant",
    "Công ty TNHH Kiểm toán Tư vấn Rồng Việt": "auditor",
}

PROJECT: dict[str, Any] = {
    "code": "8200685",
    "short_name": "Cấp xã Lâm Đồng",
    "project_type": "procurement",
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


def _consulting(
    number: int,
    org: str,
    value: int,
    start: date,
    end: date,
    days: int,
    *,
    contract_no: str,
    role: str | None = None,
    note: str | None = None,
) -> PackageSeed:
    """A consulting package as listed in "Sửa thông tin trên web": firm, value, start–end, days.

    The end date is the one in that list (start + days, not start + days - 1), so it overrides
    the computed one.
    """
    price = D(value)
    return PackageSeed(
        number,
        price,
        "consulting",
        {
            **_SIGNED,
            "winning_price": price,
            "winning_org_text": org,
            "approved_duration_days": days,
            "consulting_role": role,
        },
        ContractSeed(
            contract_no,
            {
                "effective_date": start,
                "duration_days": days,
                "planned_end_date": end,
                "end_date_override": True,
                "value": price,
                "data_quality_note": note,
            },
            (PartySeed(org, "sole"),),
        ),
    )


_LIST_NOTE = "Theo danh sách nhà thầu, giá trị và thời gian thực hiện các gói thầu (bản sửa)."

PACKAGES: tuple[PackageSeed, ...] = (
    _consulting(
        1,
        "Công ty Cổ phần Tư vấn Quang Trung",
        556_000_000,
        date(2026, 6, 15),
        date(2026, 7, 30),
        45,
        contract_no="53",
        note=_LIST_NOTE,
    ),
    _consulting(
        2,
        "Công ty TNHH Hưng Dũng Lâm Đồng",
        70_000_000,
        date(2026, 6, 15),
        date(2026, 7, 15),
        30,
        contract_no="54",
        note=_LIST_NOTE,
    ),
    PackageSeed(
        3,
        D(430_000_000),
        "consulting",
        {
            **_SIGNED,
            "winning_price": D(430_000_000),
            "winning_org_text": BTA,
            "approved_duration_days": 30,
            "scope_summary": "Tư vấn thẩm định giá (nhiệm vụ chuẩn bị đầu tư).",
            "kh_lcnt_decision": "KHLCNT PL2600169648; QĐ 151/QĐ-SKHCN ngày 13/6/2026",
            "approval_decision": "QĐ 154/QĐ-SKHCN ngày 15/6/2026 (phê duyệt KQLCNT)",
            "notes": (
                "Giá trị đã bao gồm VAT 10%. Chưa rõ nghiệm thu, thanh lý, thanh toán. "
                "Chứng thư thẩm định giá 194.717.303.146 đ (20/6/2026) hiệu lực đến khoảng "
                "20/9/2026 [OCR]. QĐ 154 ghi nhầm tên dự án, cần đính chính."
            ),
        },
        ContractSeed(
            "41/2026/SKH&CNLĐ-BTA",
            {
                "signed_date": date(2026, 6, 15),
                "duration_days": 30,
                "planned_end_date": date(2026, 7, 14),
                "contract_type": "lump_sum",
                "value": D(430_000_000),
                "payment_terms_text": (
                    "Thanh toán một lần 430.000.000 đ sau nghiệm thu, thanh lý và khi dự án "
                    "được phê duyệt; không tạm ứng. Hóa đơn số 87 (2C26TBT) ngày 30/6/2026."
                ),
                "data_quality_note": (
                    "Văn bản ghi thời gian thực hiện ba cách: từ ngày hiệu lực, từ ngày ký, "
                    "30 ngày làm việc từ khi đủ hồ sơ; tính theo ngày ký."
                ),
            },
            (PartySeed(BTA, "sole"),),
        ),
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
    _consulting(
        7,
        "Sài Gòn Mới",
        509_000_000,
        date(2026, 9, 15),
        date(2026, 12, 14),
        90,
        contract_no="73",
        role="tvgs",
        note=_LIST_NOTE,
    ),
    _consulting(
        8,
        "Công ty TNHH Kiểm toán Tư vấn Rồng Việt",
        710_000_000,
        date(2026, 9, 15),
        date(2026, 12, 14),
        90,
        contract_no="74",
        role="other",
        note=_LIST_NOTE + " Giá trị: bảy trăm mười triệu đồng chẵn.",
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


def _backfill(obj: Package | Contract | Project, fields: dict[str, Any]) -> None:
    """Fill columns added after the first seed; values someone already entered are kept."""
    for key, value in fields.items():
        if getattr(obj, key) is None:
            setattr(obj, key, value)


async def capxa_project(session: AsyncSession) -> Project | None:
    """The commune-level project the other seeds hang their data on."""
    return (
        await session.execute(select(Project).where(Project.code == PROJECT["code"]))
    ).scalar_one_or_none()


async def ensure_members(session: AsyncSession, project: Project) -> int:
    """Seat every non-admin user in a project nobody works on yet, with their account role.

    A project that already has members is left alone, so removing someone in the application is
    not undone by the next seed. System admins need no seat: they see every project.
    """
    taken = (
        await session.execute(
            select(ProjectMember.id).where(ProjectMember.project_id == project.id).limit(1)
        )
    ).first()
    if taken is not None:
        return 0
    added = 0
    for user in (await session.execute(select(User).where(User.role != "admin"))).scalars():
        session.add(ProjectMember(project_id=project.id, user_id=user.id, role=user.role))
        added += 1
    await session.flush()
    return added


async def seed_project(session: AsyncSession) -> Project:
    investor = await _org(session, INVESTOR, "investor")
    orgs = {name: await _org(session, name, kind) for name, kind in CONTRACTORS.items()}

    project = await capxa_project(session)
    if project is None:
        project = Project(investor_org_id=investor.id, **PROJECT)
        session.add(project)
        await session.flush()
    else:
        _backfill(project, {"investor_org_id": investor.id, **PROJECT})  # a bare project row
    await ensure_members(session, project)

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
