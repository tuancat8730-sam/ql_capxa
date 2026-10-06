"""Guarantee rules (SPEC 7.1 GUARANTEE_*, ADVANCE_GUARANTEE_SHORT and 7.2 statuses).

Pure functions: the M7 alert engine reuses them to persist alerts, the API uses them to show
findings next to each contract today.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

DEFAULT_PAYMENT_TERM_DAYS = 7
EXPIRING_DAYS = 10
CRITICAL_DAYS = 3
MISSING_GRACE_DAYS = 7

# Manual states: dates never override them.
_MANUAL = frozenset({"released", "missing", "pending"})
# Guarantees whose expiry should still be watched (a bid guarantee is returned after award).
_WATCHED_TYPES = frozenset({"performance", "advance", "warranty"})

Severity = Literal["warning", "critical"]


@dataclass(frozen=True)
class ContractTimeline:
    start: date | None  # effective date, else signed date
    end: date | None  # extended end date, else planned end date
    advance_amount: Decimal | None
    recovered_amount: Decimal


@dataclass(frozen=True)
class GuaranteeFacts:
    id: str
    guarantee_type: str
    status: str  # stored status
    expiry_date: date | None
    required: bool


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    guarantee_id: str | None = None
    due_date: date | None = None


def guarantee_status(stored: str, expiry_date: date | None, today: date) -> str:
    """SPEC 7.2: valid (>10 days left), expiring (<=10), expired, released, missing."""
    if stored in _MANUAL:
        return stored
    if expiry_date is None:
        return "valid"
    days = (expiry_date - today).days
    if days < 0:
        return "expired"
    return "expiring" if days <= EXPIRING_DAYS else "valid"


def _outstanding_advance(contract: ContractTimeline) -> Decimal:
    advance = contract.advance_amount or Decimal(0)
    return max(advance - contract.recovered_amount, Decimal(0))


def _watched(g: GuaranteeFacts) -> bool:
    return g.status not in _MANUAL and g.guarantee_type in _WATCHED_TYPES


def check_guarantees(
    contract: ContractTimeline,
    guarantees: list[GuaranteeFacts],
    today: date,
    *,
    payment_term_days: int = DEFAULT_PAYMENT_TERM_DAYS,
) -> list[Finding]:
    findings: list[Finding] = []

    for g in guarantees:
        # GUARANTEE_EXPIRING: <=10 days warning; <=3 days or already expired critical
        if _watched(g) and g.expiry_date is not None:
            days = (g.expiry_date - today).days
            if days <= EXPIRING_DAYS:
                critical = days <= CRITICAL_DAYS
                findings.append(
                    Finding(
                        "GUARANTEE_EXPIRING",
                        "critical" if critical else "warning",
                        "Bảo lãnh đã hết hạn" if days < 0 else f"Bảo lãnh còn {days} ngày hết hạn",
                        guarantee_id=g.id,
                        due_date=g.expiry_date,
                    )
                )

        # ADVANCE_GUARANTEE_SHORT: advance still owed but guarantee ends before contract end + term
        if (
            g.guarantee_type == "advance"
            and _watched(g)
            and g.expiry_date is not None
            and contract.end is not None
            and _outstanding_advance(contract) > 0
        ):
            needed_until = contract.end + timedelta(days=payment_term_days)
            if g.expiry_date < needed_until:
                findings.append(
                    Finding(
                        "ADVANCE_GUARANTEE_SHORT",
                        "critical",
                        "Bảo lãnh tạm ứng hết hạn trước ngày kết thúc hợp đồng "
                        f"+ {payment_term_days} ngày thanh toán",
                        guarantee_id=g.id,
                        due_date=needed_until,
                    )
                )

        # GUARANTEE_MISSING: an expected (required) guarantee that has not been entered
        if g.status == "missing" and g.required and _missing_applies(g, contract, today):
            label = "tạm ứng" if g.guarantee_type == "advance" else "thực hiện hợp đồng"
            findings.append(
                Finding(
                    "GUARANTEE_MISSING", "critical", f"Chưa có bảo lãnh {label}", guarantee_id=g.id
                )
            )

    return findings


def _missing_applies(g: GuaranteeFacts, contract: ContractTimeline, today: date) -> bool:
    if g.guarantee_type == "advance":
        return (contract.advance_amount or Decimal(0)) > 0
    if g.guarantee_type == "performance":
        return contract.start is None or today > contract.start + timedelta(days=MISSING_GRACE_DAYS)
    return False
