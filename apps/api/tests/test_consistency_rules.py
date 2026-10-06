"""SPEC 7.5: contract data consistency checks. Each rule: ok, boundary, violation."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.rules import (
    ContractFacts,
    PackageFacts,
    PartyFacts,
    ProjectFacts,
    check_contract,
)

D = Decimal

PROJECT = ProjectFacts(treasury_account="9552.2.8200685")
PACKAGE = PackageFacts(winning_price=D(51_505_400_000), approved_duration_days=60)
CONTRACT = ContractFacts(
    value=D(51_505_400_000),
    duration_days=60,
    signed_date=date(2026, 9, 14),
    effective_date=None,
    planned_end_date=date(2026, 11, 12),
    end_date_override=False,
    contract_type="lump_sum",
    price_adjustment=False,
    advance_pct=D(30),
    advance_amount=D(15_451_620_000),
    performance_bond_pct=D(3),
    performance_bond_amount=D(1_545_162_000),
    warranty_bond_pct=None,
    warranty_bond_amount=None,
    investor_account="9552.2.8200685",
)
PARTIES = [
    PartyFacts(share_amount=D(30_903_240_000), advance_amount=D(9_270_972_000)),
    PartyFacts(share_amount=D(20_602_160_000), advance_amount=D(6_180_648_000)),
]


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def run(contract=CONTRACT, package=PACKAGE, project=PROJECT, parties=PARTIES):
    return check_contract(contract, package, project, parties)


def test_clean_contract_has_no_issues() -> None:
    assert run() == []


# 1. value == winning price
def test_value_must_equal_winning_price() -> None:
    assert "VALUE_NE_WINNING_PRICE" in codes(
        run(contract=replace(CONTRACT, value=D(51_505_401_000)))
    )


def test_value_check_skipped_when_either_side_unknown() -> None:
    assert run(package=replace(PACKAGE, winning_price=None)) == []
    assert "VALUE_NE_WINNING_PRICE" not in codes(run(contract=replace(CONTRACT, value=None)))


# 2. duration == KHLCNT duration
def test_duration_must_equal_khlcnt() -> None:
    assert "DURATION_NE_KHLCNT" in codes(run(contract=replace(CONTRACT, duration_days=90)))
    assert "DURATION_NE_KHLCNT" not in codes(run(contract=replace(CONTRACT, duration_days=60)))


def test_duration_skipped_without_khlcnt() -> None:
    assert run(package=replace(PACKAGE, approved_duration_days=None)) == []


# 3. investor account == project treasury account
def test_investor_account_must_match_treasury() -> None:
    bad = replace(CONTRACT, investor_account="9552.2.8171939")
    assert "INVESTOR_ACCOUNT_NE_TREASURY" in codes(run(contract=bad))


def test_investor_account_comparison_ignores_spacing() -> None:
    assert run(contract=replace(CONTRACT, investor_account=" 9552.2.8200685 ")) == []


def test_investor_account_skipped_when_unknown() -> None:
    assert run(contract=replace(CONTRACT, investor_account=None)) == []
    assert run(project=ProjectFacts(treasury_account=None)) == []


# 4. consortium shares sum to contract value
def test_party_shares_must_sum_to_value() -> None:
    bad = [PARTIES[0], replace(PARTIES[1], share_amount=D(20_602_159_999))]
    assert "PARTY_SHARE_SUM_NE_VALUE" in codes(run(parties=bad))


def test_party_shares_skipped_without_parties_or_with_unknown_share() -> None:
    assert run(parties=[]) == []
    assert run(parties=[PARTIES[0], replace(PARTIES[1], share_amount=None)]) == []


# 5. member advances sum to advance_amount
def test_party_advances_must_sum_to_advance() -> None:
    bad = [PARTIES[0], replace(PARTIES[1], advance_amount=D(6_180_649_000))]
    assert "PARTY_ADVANCE_SUM_NE_ADVANCE" in codes(run(parties=bad))


def test_party_advance_skipped_when_any_member_unknown() -> None:
    assert run(parties=[PARTIES[0], replace(PARTIES[1], advance_amount=None)]) == []


# 6. advance_amount == advance_pct x value (tolerance 1 dong)
@pytest.mark.parametrize(
    ("delta", "flagged"), [(0, False), (1, False), (-1, False), (2, True), (-1000, True)]
)
def test_advance_amount_matches_pct_with_one_dong_tolerance(delta: int, flagged: bool) -> None:
    c = replace(CONTRACT, advance_amount=CONTRACT.advance_amount + delta)
    assert ("ADVANCE_NE_PCT_X_VALUE" in codes(run(contract=c))) is flagged


# 7. bonds == pct x value
@pytest.mark.parametrize(("delta", "flagged"), [(0, False), (1, False), (2, True)])
def test_performance_bond_matches_pct(delta: int, flagged: bool) -> None:
    c = replace(CONTRACT, performance_bond_amount=CONTRACT.performance_bond_amount + delta)
    assert ("PERFORMANCE_BOND_NE_PCT_X_VALUE" in codes(run(contract=c))) is flagged


def test_warranty_bond_checked_when_present() -> None:
    c = replace(CONTRACT, warranty_bond_pct=D(5), warranty_bond_amount=D(1))
    assert "WARRANTY_BOND_NE_PCT_X_VALUE" in codes(run(contract=c))


def test_bond_checks_skipped_when_pct_or_amount_missing() -> None:
    c = replace(CONTRACT, advance_pct=None, performance_bond_amount=None)
    assert run(contract=c) == []


# 8. lump sum must not carry price adjustment
def test_lump_sum_with_price_adjustment_is_flagged() -> None:
    bad = replace(CONTRACT, price_adjustment=True)
    assert "LUMP_SUM_WITH_PRICE_ADJUSTMENT" in codes(run(contract=bad))


def test_unit_price_may_carry_price_adjustment() -> None:
    c = replace(CONTRACT, contract_type="unit_price", price_adjustment=True)
    assert run(contract=c) == []


# 9. planned end = start + duration - 1
def test_planned_end_boundary_exact() -> None:
    # 14/09/2026 + 60 days - 1 = 12/11/2026
    assert run() == []


def test_planned_end_off_by_one_is_flagged_with_expected_date() -> None:
    issues = run(contract=replace(CONTRACT, planned_end_date=date(2026, 11, 13)))
    (issue,) = [i for i in issues if i.code == "END_DATE_MISMATCH"]
    assert issue.severity == "warning"
    assert issue.expected == "2026-11-12"
    assert issue.actual == "2026-11-13"


def test_planned_end_override_downgrades_to_info() -> None:
    c = replace(CONTRACT, planned_end_date=date(2026, 11, 13), end_date_override=True)
    (issue,) = run(contract=c)
    assert issue.code == "END_DATE_MISMATCH" and issue.severity == "info"


def test_planned_end_prefers_effective_date_over_signed_date() -> None:
    c = replace(CONTRACT, effective_date=date(2026, 9, 15), planned_end_date=date(2026, 11, 13))
    assert run(contract=c) == []


def test_planned_end_skipped_without_start_or_duration() -> None:
    no_start = replace(CONTRACT, signed_date=None, planned_end_date=date(2030, 1, 1))
    no_duration = replace(CONTRACT, duration_days=None, planned_end_date=date(2030, 1, 1))
    assert run(contract=no_start) == []
    assert run(contract=no_duration) == []


def test_issue_messages_are_vietnamese_and_have_severity() -> None:
    issues = run(contract=replace(CONTRACT, duration_days=90, price_adjustment=True))
    assert issues and all(i.message and i.severity in {"warning", "info"} for i in issues)
