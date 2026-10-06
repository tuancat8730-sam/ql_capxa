"""Business rules (SPEC section 7): pure functions over plain facts, trivially testable."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

Severity = Literal["warning", "info"]

ONE_DONG = Decimal(1)
ZERO = Decimal(0)


@dataclass(frozen=True)
class ProjectFacts:
    treasury_account: str | None


@dataclass(frozen=True)
class PackageFacts:
    winning_price: Decimal | None
    approved_duration_days: int | None


@dataclass(frozen=True)
class PartyFacts:
    share_amount: Decimal | None
    advance_amount: Decimal | None


@dataclass(frozen=True)
class ContractFacts:
    value: Decimal | None
    duration_days: int | None
    signed_date: date | None
    effective_date: date | None
    planned_end_date: date | None
    end_date_override: bool
    contract_type: str | None
    price_adjustment: bool
    advance_pct: Decimal | None
    advance_amount: Decimal | None
    performance_bond_pct: Decimal | None
    performance_bond_amount: Decimal | None
    warranty_bond_pct: Decimal | None
    warranty_bond_amount: Decimal | None
    investor_account: str | None


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    message: str
    expected: str | None = None
    actual: str | None = None


def _differs(a: Decimal, b: Decimal, tolerance: Decimal = ZERO) -> bool:
    return abs(a - b) > tolerance


def _normalize_account(value: str) -> str:
    return "".join(value.split())


def _pct_amount(pct: Decimal, value: Decimal) -> Decimal:
    return pct * value / 100


def _pct_amount_issue(
    code: str, label: str, pct: Decimal | None, amount: Decimal | None, value: Decimal | None
) -> Issue | None:
    if pct is None or amount is None or value is None:
        return None
    expected = _pct_amount(pct, value)
    if _differs(amount, expected, ONE_DONG):
        return Issue(
            code,
            "warning",
            f"{label} không bằng {pct}% giá trị hợp đồng",
            expected=f"{expected:.0f}",
            actual=f"{amount:.0f}",
        )
    return None


def check_contract(
    contract: ContractFacts,
    package: PackageFacts,
    project: ProjectFacts,
    parties: list[PartyFacts],
) -> list[Issue]:
    """The nine consistency checks of SPEC 7.5. A check is skipped when an input is unknown."""
    issues: list[Issue] = []

    # 1. contract value equals the winning price of the package
    if (
        contract.value is not None
        and package.winning_price is not None
        and _differs(contract.value, package.winning_price)
    ):
        issues.append(
            Issue(
                "VALUE_NE_WINNING_PRICE",
                "warning",
                "Giá trị hợp đồng khác giá trúng thầu của gói",
                expected=f"{package.winning_price:.0f}",
                actual=f"{contract.value:.0f}",
            )
        )

    # 2. duration equals the duration in the procurement plan (KHLCNT)
    if (
        contract.duration_days is not None
        and package.approved_duration_days is not None
        and contract.duration_days != package.approved_duration_days
    ):
        issues.append(
            Issue(
                "DURATION_NE_KHLCNT",
                "warning",
                "Thời gian thực hiện khác thời gian trong KHLCNT",
                expected=str(package.approved_duration_days),
                actual=str(contract.duration_days),
            )
        )

    # 3. investor account equals the project treasury account
    if (
        contract.investor_account
        and project.treasury_account
        and _normalize_account(contract.investor_account)
        != _normalize_account(project.treasury_account)
    ):
        issues.append(
            Issue(
                "INVESTOR_ACCOUNT_NE_TREASURY",
                "warning",
                "Tài khoản chủ đầu tư khác tài khoản kho bạc của dự án",
                expected=project.treasury_account,
                actual=contract.investor_account,
            )
        )

    # 4. consortium shares sum to the contract value
    if contract.value is not None and parties and all(p.share_amount is not None for p in parties):
        total = sum((p.share_amount for p in parties if p.share_amount is not None), ZERO)
        if _differs(total, contract.value):
            issues.append(
                Issue(
                    "PARTY_SHARE_SUM_NE_VALUE",
                    "warning",
                    "Tổng phần giá trị các thành viên liên danh khác giá trị hợp đồng",
                    expected=f"{contract.value:.0f}",
                    actual=f"{total:.0f}",
                )
            )

    # 5. member advances sum to the contract advance
    if (
        contract.advance_amount is not None
        and parties
        and all(p.advance_amount is not None for p in parties)
    ):
        total = sum((p.advance_amount for p in parties if p.advance_amount is not None), ZERO)
        if _differs(total, contract.advance_amount):
            issues.append(
                Issue(
                    "PARTY_ADVANCE_SUM_NE_ADVANCE",
                    "warning",
                    "Tổng tạm ứng các thành viên khác số tạm ứng của hợp đồng",
                    expected=f"{contract.advance_amount:.0f}",
                    actual=f"{total:.0f}",
                )
            )

    # 6 and 7. advance and bonds equal pct x value (1 dong tolerance)
    for issue in (
        _pct_amount_issue(
            "ADVANCE_NE_PCT_X_VALUE",
            "Số tiền tạm ứng",
            contract.advance_pct,
            contract.advance_amount,
            contract.value,
        ),
        _pct_amount_issue(
            "PERFORMANCE_BOND_NE_PCT_X_VALUE",
            "Bảo đảm thực hiện hợp đồng",
            contract.performance_bond_pct,
            contract.performance_bond_amount,
            contract.value,
        ),
        _pct_amount_issue(
            "WARRANTY_BOND_NE_PCT_X_VALUE",
            "Bảo đảm bảo hành",
            contract.warranty_bond_pct,
            contract.warranty_bond_amount,
            contract.value,
        ),
    ):
        if issue:
            issues.append(issue)

    # 8. a lump-sum contract must not carry price adjustment
    if contract.contract_type == "lump_sum" and contract.price_adjustment:
        issues.append(
            Issue(
                "LUMP_SUM_WITH_PRICE_ADJUSTMENT",
                "warning",
                "Hợp đồng trọn gói không được ghi điều chỉnh giá",
            )
        )

    # 9. planned end = start + duration - 1 (may be overridden on purpose)
    start = contract.effective_date or contract.signed_date
    if start and contract.duration_days and contract.planned_end_date:
        expected_end = start + timedelta(days=contract.duration_days - 1)
        if contract.planned_end_date != expected_end:
            issues.append(
                Issue(
                    "END_DATE_MISMATCH",
                    "info" if contract.end_date_override else "warning",
                    "Ngày kết thúc khác (ngày bắt đầu + thời gian − 1)"
                    + (" – đã ghi đè có chủ ý" if contract.end_date_override else ""),
                    expected=expected_end.isoformat(),
                    actual=contract.planned_end_date.isoformat(),
                )
            )

    return issues
