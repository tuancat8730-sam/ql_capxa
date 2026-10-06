"""SPEC 7.1 / 7.2 guarantee rules. Each rule: ok, boundary, violation."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.guarantee_rules import (
    ContractTimeline,
    GuaranteeFacts,
    check_guarantees,
    guarantee_status,
)

D = Decimal
TODAY = date(2026, 11, 5)


# --- 7.2 status ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (-1, "expired"),
        (0, "expiring"),
        (1, "expiring"),
        (10, "expiring"),
        (11, "valid"),
        (60, "valid"),
    ],
)
def test_status_from_expiry_boundaries(days: int, expected: str) -> None:
    assert guarantee_status("valid", TODAY + timedelta(days=days), TODAY) == expected


def test_status_without_expiry_is_valid_until_acceptance() -> None:
    assert guarantee_status("valid", None, TODAY) == "valid"


@pytest.mark.parametrize("stored", ["released", "missing", "pending"])
def test_manual_states_are_never_overridden_by_dates(stored: str) -> None:
    assert guarantee_status(stored, TODAY - timedelta(days=100), TODAY) == stored


# --- fixtures --------------------------------------------------------------------------------

CONTRACT = ContractTimeline(
    start=date(2026, 9, 14),
    end=date(2026, 11, 12),
    advance_amount=D(4_079_992_500),
    recovered_amount=D(0),
)


def g(
    kind: str,
    *,
    status: str = "valid",
    expiry: date | None = None,
    required: bool = True,
    gid: str = "g1",
):
    return GuaranteeFacts(
        id=gid, guarantee_type=kind, status=status, expiry_date=expiry, required=required
    )


def codes(findings) -> list[str]:
    return [f.code for f in findings]


def run(guarantees, contract=CONTRACT, today=TODAY, term=7):
    return check_guarantees(contract, guarantees, today, payment_term_days=term)


# --- GUARANTEE_EXPIRING ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "severity"),
    [
        (-5, "critical"),
        (-1, "critical"),
        (0, "critical"),
        (3, "critical"),
        (4, "warning"),
        (10, "warning"),
        (11, None),
    ],
)
def test_expiring_severity_boundaries(days: int, severity: str | None) -> None:
    contract = replace(CONTRACT, advance_amount=D(0))  # isolate from the advance rule
    findings = run([g("performance", expiry=TODAY + timedelta(days=days))], contract)
    expiring = [f for f in findings if f.code == "GUARANTEE_EXPIRING"]
    assert [f.severity for f in expiring] == ([severity] if severity else [])


def test_expiring_ignores_released_missing_bid_and_open_ended() -> None:
    contract = replace(CONTRACT, advance_amount=D(0))
    near = TODAY + timedelta(days=2)
    assert run([g("performance", status="released", expiry=near)], contract) == []
    assert run([g("performance", status="missing", expiry=near, required=False)], contract) == []
    assert run([g("bid", expiry=near)], contract) == []
    assert run([g("warranty", expiry=None)], contract) == []


# --- ADVANCE_GUARANTEE_SHORT -----------------------------------------------------------------


def test_spec_14_4_package_05_advance_guarantee_is_short() -> None:
    # TPBank expires 13/11/2026; contract ends 12/11/2026 + 7 days payment term = 19/11/2026
    tpbank = g("advance", expiry=date(2026, 11, 13), gid="tpbank")
    findings = run([tpbank], today=date(2026, 11, 5))
    short = [f for f in findings if f.code == "ADVANCE_GUARANTEE_SHORT"]
    assert [(f.severity, f.guarantee_id) for f in short] == [("critical", "tpbank")]
    # 8 days before expiry -> also "expiring" (warning), as SPEC M3 acceptance expects
    assert [f.severity for f in findings if f.code == "GUARANTEE_EXPIRING"] == ["warning"]


@pytest.mark.parametrize(("offset", "flagged"), [(-1, True), (0, False), (1, False)])
def test_advance_short_boundary_is_end_plus_payment_term(offset: int, flagged: bool) -> None:
    expiry = CONTRACT.end + timedelta(days=7 + offset)  # type: ignore[operator]
    findings = run([g("advance", expiry=expiry)], today=date(2026, 9, 20))
    assert ("ADVANCE_GUARANTEE_SHORT" in codes(findings)) is flagged


def test_advance_short_uses_custom_payment_term() -> None:
    expiry = CONTRACT.end + timedelta(days=10)  # type: ignore[operator]
    assert "ADVANCE_GUARANTEE_SHORT" not in codes(
        run([g("advance", expiry=expiry)], term=7, today=date(2026, 9, 20))
    )
    assert "ADVANCE_GUARANTEE_SHORT" in codes(
        run([g("advance", expiry=expiry)], term=14, today=date(2026, 9, 20))
    )


def test_advance_short_not_raised_once_advance_fully_recovered() -> None:
    contract = replace(CONTRACT, recovered_amount=CONTRACT.advance_amount)
    findings = run([g("advance", expiry=date(2026, 11, 13))], contract, today=date(2026, 9, 20))
    assert "ADVANCE_GUARANTEE_SHORT" not in codes(findings)


def test_advance_short_skipped_when_contract_end_or_expiry_unknown() -> None:
    no_end = replace(CONTRACT, end=None)
    assert run([g("advance", expiry=date(2026, 11, 13))], no_end, today=date(2026, 9, 20)) == []
    assert "ADVANCE_GUARANTEE_SHORT" not in codes(
        run([g("advance", expiry=None)], today=date(2026, 9, 20))
    )


def test_advance_short_checks_each_guarantee_separately() -> None:
    both = [
        g("advance", expiry=date(2026, 11, 13), gid="tpbank"),
        g("advance", expiry=date(2026, 11, 13), gid="bidv"),
    ]
    flagged = [
        f.guarantee_id
        for f in run(both, today=date(2026, 9, 20))
        if f.code == "ADVANCE_GUARANTEE_SHORT"
    ]
    assert flagged == ["tpbank", "bidv"]


# --- GUARANTEE_MISSING -----------------------------------------------------------------------


def test_missing_advance_guarantee_is_critical_when_advance_exists() -> None:
    findings = run([g("advance", status="missing", gid="adv")], today=date(2026, 9, 14))
    assert [(f.code, f.severity, f.guarantee_id) for f in findings] == [
        ("GUARANTEE_MISSING", "critical", "adv")
    ]


def test_missing_advance_not_raised_without_advance() -> None:
    contract = replace(CONTRACT, advance_amount=D(0))
    assert run([g("advance", status="missing")], contract) == []


@pytest.mark.parametrize(
    ("days_after_start", "flagged"), [(6, False), (7, False), (8, True), (30, True)]
)
def test_missing_performance_bond_only_after_effective_plus_seven_days(
    days_after_start: int, flagged: bool
) -> None:
    today = CONTRACT.start + timedelta(days=days_after_start)  # type: ignore[operator]
    contract = replace(CONTRACT, advance_amount=D(0))
    findings = run([g("performance", status="missing")], contract, today=today)
    assert ("GUARANTEE_MISSING" in codes(findings)) is flagged


def test_missing_performance_bond_with_unknown_start_is_flagged() -> None:
    contract = replace(CONTRACT, start=None, advance_amount=D(0))
    assert "GUARANTEE_MISSING" in codes(run([g("performance", status="missing")], contract))


def test_missing_rule_requires_the_row_to_be_required() -> None:
    contract = replace(CONTRACT, advance_amount=D(0))
    far = CONTRACT.start + timedelta(days=100)  # type: ignore[operator]
    assert run([g("performance", status="missing", required=False)], contract, today=far) == []


def test_missing_warranty_and_bid_are_not_alerted() -> None:
    contract = replace(CONTRACT, advance_amount=D(0))
    far = CONTRACT.start + timedelta(days=100)  # type: ignore[operator]
    assert (
        run([g("warranty", status="missing"), g("bid", status="missing")], contract, today=far)
        == []
    )


def test_findings_have_vietnamese_messages_and_due_dates() -> None:
    findings = run([g("advance", expiry=date(2026, 11, 8))], today=TODAY)
    assert findings and all(f.message for f in findings)
    assert all(f.due_date == date(2026, 11, 8) for f in findings if f.code == "GUARANTEE_EXPIRING")
