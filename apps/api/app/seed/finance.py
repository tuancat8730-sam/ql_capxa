"""Seed guarantees and payments from SPEC 14.4 and 14.5. Unknowns stay NULL. Idempotent."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contract, Guarantee, Package, Payment

D = Decimal


@dataclass(frozen=True)
class GuaranteeSeed:
    contract_no: str
    guarantee_type: str
    amount: Decimal
    status: str = "valid"
    bank_name: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    verified: bool = False
    verify_note: str | None = None
    validity_text: str | None = None


@dataclass(frozen=True)
class PaymentSeed:
    contract_no: str
    payment_type: str
    seq: int
    amount: Decimal
    notes: str | None = field(default=None)


GUARANTEES: tuple[GuaranteeSeed, ...] = (
    GuaranteeSeed(
        "71",
        "performance",
        D(1_545_162_000),
        bank_name="ABBank",
        issue_date=date(2026, 9, 12),
        verify_note=(
            "Bản scan [OCR] từng đọc 1.515.162.000; đúng là 1.545.162.000 = 3% × giá trị. "
            "Cần đối chiếu bản gốc."
        ),
    ),
    GuaranteeSeed(
        "72",
        "advance",
        D(2_815_942_500),
        bank_name="TPBank",
        issue_date=date(2026, 9, 15),
        expiry_date=date(2026, 11, 13),
        verify_note="Ngày hết hạn đọc từ bản scan [OCR]; cần đối chiếu bản gốc.",
    ),
    GuaranteeSeed(
        "72",
        "advance",
        D(1_264_050_000),
        bank_name="BIDV",
        expiry_date=date(2026, 11, 13),
        verify_note="Bản scan [OCR] ghi hết hạn ≤ 13/11/2026; dùng 13/11/2026 làm cận trên.",
    ),
    GuaranteeSeed(
        "71",
        "advance",
        D(15_451_620_000),
        status="missing",
        verify_note="Chưa có bảo lãnh tạm ứng (SPEC 14.4).",
    ),
    GuaranteeSeed(
        "72",
        "performance",
        D(407_999_250),
        status="missing",
        verify_note="Chưa có bảo đảm thực hiện hợp đồng (SPEC 14.4).",
    ),
)

PAYMENTS: tuple[PaymentSeed, ...] = (
    PaymentSeed("80", "advance", 0, D(518_076_000)),
    PaymentSeed("80", "payment", 1, D(1_554_228_000)),
    PaymentSeed("80", "payment", 2, D(172_692_000)),
    PaymentSeed("71", "advance", 0, D(15_451_620_000)),
    PaymentSeed("71", "payment", 1, D(20_602_160_000), "Đợt còn lại theo hợp đồng."),
)


async def _contract(session: AsyncSession, contract_no: str) -> Contract:
    return (
        await session.execute(
            select(Contract)
            .join(Package, Package.id == Contract.package_id)
            .where(Contract.contract_no == contract_no)
        )
    ).scalar_one()


async def seed_finance(session: AsyncSession) -> None:
    """Requires `seed_project` to have run first."""
    for g in GUARANTEES:
        contract = await _contract(session, g.contract_no)
        exists = (
            await session.execute(
                select(Guarantee.id).where(
                    Guarantee.contract_id == contract.id,
                    Guarantee.guarantee_type == g.guarantee_type,
                    Guarantee.amount == g.amount,
                )
            )
        ).first()
        if exists:
            continue
        session.add(
            Guarantee(
                contract_id=contract.id,
                guarantee_type=g.guarantee_type,
                amount=g.amount,
                status=g.status,
                bank_name=g.bank_name,
                issue_date=g.issue_date,
                expiry_date=g.expiry_date,
                verified=g.verified,
                verify_note=g.verify_note,
                validity_text=g.validity_text,
                required=True,
            )
        )
    for p in PAYMENTS:
        contract = await _contract(session, p.contract_no)
        exists = (
            await session.execute(
                select(Payment.id).where(
                    Payment.contract_id == contract.id,
                    Payment.payment_type == p.payment_type,
                    Payment.seq == p.seq,
                )
            )
        ).first()
        if exists:
            continue
        session.add(
            Payment(
                contract_id=contract.id,
                payment_type=p.payment_type,
                seq=p.seq,
                amount=p.amount,
                status="planned",
                notes=p.notes,
            )
        )
    await session.commit()
