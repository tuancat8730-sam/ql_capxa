from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import pytest

from app.services import alert_rules as r

TODAY = date(2026, 11, 5)  # a Thursday


def _kinds(cands: list[r.Candidate]) -> list[tuple[str, str]]:
    return [(c.alert_type, c.severity) for c in cands]


# --- CONTRACT_ENDING ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days_left", "expected"),
    [
        (15, []),
        (14, [("CONTRACT_ENDING", "warning")]),
        (6, [("CONTRACT_ENDING", "warning")]),
        (5, [("CONTRACT_ENDING", "critical")]),
        (0, [("CONTRACT_ENDING", "critical")]),
        (-3, [("CONTRACT_ENDING", "critical")]),
    ],
)
def test_contract_ending_boundaries(days_left: int, expected: list[tuple[str, str]]) -> None:
    out = r.contract_ending(
        contract_id="c1",
        package_id="p1",
        package_label="Gói 01",
        end=TODAY + timedelta(days=days_left),
        progress_pct=D(40),
        today=TODAY,
    )
    assert _kinds(out) == expected


def test_contract_ending_quiet_when_done_or_no_date() -> None:
    done = r.contract_ending(
        contract_id="c",
        package_id="p",
        package_label="G",
        end=TODAY,
        progress_pct=D(100),
        today=TODAY,
    )
    no_date = r.contract_ending(
        contract_id="c",
        package_id="p",
        package_label="G",
        end=None,
        progress_pct=D(10),
        today=TODAY,
    )
    assert done == [] and no_date == []


# --- STAGE_DELAYED -----------------------------------------------------------------------------


def _stage(planned_end: date | None, *, status: str = "in_progress", pct: int = 50):
    return r.stage_delayed(
        stage_id="s",
        package_id="p",
        package_label="G",
        stage_name="Thực hiện",
        status=status,
        planned_end=planned_end,
        progress_pct=D(pct),
        today=TODAY,
    )


def test_stage_delayed_boundaries() -> None:
    assert _stage(TODAY) == []  # ends today: not yet late
    assert _kinds(_stage(TODAY - timedelta(days=1))) == [("STAGE_DELAYED", "warning")]
    assert _stage(TODAY - timedelta(days=9), status="done") == []
    assert _stage(TODAY - timedelta(days=9), pct=100) == []
    assert _stage(None) == []


# --- planned progress / PROGRESS_BEHIND --------------------------------------------------------


def _sched(start: date | None, end: date | None, weight: int = 40, status: str = "in_progress"):
    return r.StageSchedule(D(weight), start, end, status)


def test_planned_fraction_is_linear_inside_the_stage() -> None:
    s = _sched(date(2026, 11, 1), date(2026, 11, 10))
    assert r.stage_planned_fraction(s, date(2026, 10, 31)) == 0
    assert r.stage_planned_fraction(s, date(2026, 11, 5)) == D("0.5")
    assert r.stage_planned_fraction(s, date(2026, 11, 10)) == 1
    assert r.stage_planned_fraction(_sched(None, None), TODAY) is None
    assert r.stage_planned_fraction(_sched(None, None, status="done"), TODAY) == 1


def test_planned_progress_weighted_and_none_when_unscheduled() -> None:
    stages = [
        _sched(date(2026, 10, 1), date(2026, 10, 31), 50, "done"),
        _sched(date(2026, 11, 1), date(2026, 11, 10), 50),
    ]
    assert r.planned_progress(stages, TODAY) == D("75.00")
    assert r.planned_progress([_sched(None, None)], TODAY) is None
    assert r.planned_progress([], TODAY) is None


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (D(90), []),  # 10 points behind exactly: quiet
        (D("89.9"), [("PROGRESS_BEHIND", "warning")]),
        (D(75), [("PROGRESS_BEHIND", "warning")]),  # 25 points: still warning
        (D("74.9"), [("PROGRESS_BEHIND", "critical")]),
        (D(100), []),
    ],
)
def test_progress_behind_boundaries(actual: D, expected: list[tuple[str, str]]) -> None:
    out = r.progress_behind(package_id="p", package_label="G", actual=actual, planned=D(100))
    assert _kinds(out) == expected


def test_progress_behind_needs_a_plan() -> None:
    assert r.progress_behind(package_id="p", package_label="G", actual=D(0), planned=None) == []


# --- ISSUE_SLA ---------------------------------------------------------------------------------

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def _issue(due_at: datetime | None, status: str = "open"):
    return r.issue_sla(
        issue_id="i", code="V-001", title="t", package_id="p", due_at=due_at, status=status, now=NOW
    )


def test_issue_sla_boundaries() -> None:
    assert _issue(NOW) == []
    assert _kinds(_issue(NOW - timedelta(minutes=1))) == [("ISSUE_SLA", "warning")]
    assert _kinds(_issue(NOW - timedelta(days=1))) == [("ISSUE_SLA", "warning")]
    assert _kinds(_issue(NOW - timedelta(days=1, seconds=1))) == [("ISSUE_SLA", "critical")]
    assert _issue(NOW - timedelta(days=3), status="resolved") == []
    assert _issue(None) == []


# --- DOC_MISSING -------------------------------------------------------------------------------


def _doc_missing(missing: list[tuple[str, str, str]], status: str = "executing"):
    return r.doc_missing(
        package_id="p",
        package_label="G",
        package_status=status,
        current_stage="S3_EXECUTION",
        missing=missing,
    )


def test_doc_missing_only_for_stages_already_entered() -> None:
    out = _doc_missing(
        [("a", "S2_SELECTION", "E-HSMT"), ("b", "S4_ACCEPTANCE", "Biên bản nghiệm thu")]
    )
    assert len(out) == 1
    assert "1 hồ sơ" in out[0].title
    assert "E-HSMT" in out[0].message
    assert "nghiệm thu" not in out[0].message


def test_doc_missing_quiet_cases() -> None:
    item = [("a", "S1_START", "x")]
    assert _doc_missing(item, "planning") == []
    assert _doc_missing(item, "cancelled") == []
    assert _doc_missing([]) == []


def test_doc_missing_truncates_long_lists() -> None:
    (alert,) = _doc_missing([(str(i), "S1_START", f"mục {i}") for i in range(5)])
    assert "và 2 mục khác" in alert.message


# --- DAILY_LOG_MISSING -------------------------------------------------------------------------


def _log(hour: int, *, has: bool = False, status: str = "executing", day: date = TODAY, hol=()):
    return r.daily_log_missing(
        package_id="p",
        package_label="G",
        package_status=status,
        has_log_today=has,
        now_local=datetime(day.year, day.month, day.day, hour, 0),
        holidays=frozenset(hol),
    )


def test_daily_log_missing_after_five_pm_on_working_days() -> None:
    assert _log(16) == []
    assert _kinds(_log(17)) == [("DAILY_LOG_MISSING", "info")]
    assert _log(18, has=True) == []
    assert _log(18, status="contract_signed") == []
    assert _log(18, day=date(2026, 11, 7)) == []  # Saturday
    assert _log(18, hol=[TODAY]) == []


def test_daily_log_fingerprint_differs_per_day() -> None:
    a = _log(18)[0]
    b = _log(18, day=date(2026, 11, 6))[0]
    assert a.fingerprint != b.fingerprint


# --- REPORT_DUE --------------------------------------------------------------------------------


def test_report_due_weekly_monthly_quarterly() -> None:
    assert r.report_due(date(2026, 11, 4)) == []
    (weekly,) = r.report_due(date(2026, 11, 6))  # Friday
    assert weekly.message.startswith("Hôm nay thứ Sáu")
    (monthly,) = r.report_due(date(2026, 11, 25))  # Wednesday
    assert "tháng 11" in monthly.message
    both = r.report_due(date(2026, 12, 25))  # Friday + 25th
    assert {c.level for c in both} == {"2026-12-25", "2026-12"}
    (quarter,) = r.report_due(date(2026, 9, 30))  # Wednesday, last day of Q3
    assert quarter.level == "2026-Q3"
    assert r.report_due(date(2026, 12, 31))[0].level == "2026-Q4"  # Thursday


# --- CROSS_PKG_DEPENDENCY ----------------------------------------------------------------------


def _ce(pid: str, ptype: str, role: str | None, end: date | None, status: str = "executing"):
    return r.ContractEnd(pid, f"Gói {pid}", ptype, role, end, status)


def test_tvgs_ending_before_last_supply_package_warns() -> None:
    contracts = [
        _ce("03", "goods", None, date(2027, 1, 20)),
        _ce("05", "goods", None, date(2026, 11, 20)),
        _ce("07", "consulting", "tvgs", date(2026, 12, 13)),
    ]
    out = r.cross_package_dependency(contracts, {}, TODAY)
    assert _kinds(out) == [("CROSS_PKG_DEPENDENCY", "warning")]
    assert out[0].package_id == "07"


def test_tvgs_covering_all_supply_is_quiet() -> None:
    contracts = [
        _ce("03", "goods", None, date(2026, 12, 1)),
        _ce("07", "consulting", "tvgs", date(2026, 12, 13)),
    ]
    assert r.cross_package_dependency(contracts, {}, TODAY) == []


def test_closed_supply_package_is_ignored() -> None:
    contracts = [
        _ce("03", "goods", None, date(2027, 6, 1), status="cancelled"),
        _ce("07", "consulting", "tvgs", date(2026, 12, 13)),
    ]
    assert r.cross_package_dependency(contracts, {}, TODAY) == []


def test_tvqlda_ending_before_planned_acceptance_warns() -> None:
    contracts = [_ce("06", "consulting", "tvqlda", date(2027, 1, 22))]
    out = r.cross_package_dependency(
        contracts, {"03": date(2027, 2, 1), "04": date(2027, 1, 1)}, TODAY
    )
    assert [c.level for c in out] == ["tvqlda"]
    assert r.cross_package_dependency(contracts, {"03": date(2027, 1, 22)}, TODAY) == []


def test_unsigned_supply_package_means_tvgs_coverage_is_unconfirmed() -> None:
    contracts = [
        _ce("03", "goods", None, None, status="bidding"),
        _ce("05", "goods", None, date(2026, 11, 12)),
        _ce("07", "consulting", "tvgs", date(2026, 12, 13)),
    ]
    (alert,) = r.cross_package_dependency(contracts, {}, TODAY)
    assert alert.package_id == "07" and "Gói 03" in alert.message
    # a TVGS contract that ends far beyond the horizon is not flagged
    far = [*contracts[:2], _ce("07", "consulting", "tvgs", date(2027, 6, 30))]
    assert r.cross_package_dependency(far, {}, TODAY) == []
    # a closed unsigned package does not count
    closed = [_ce("03", "goods", None, None, status="cancelled"), contracts[2]]
    assert r.cross_package_dependency(closed, {}, TODAY) == []


# --- PAYMENT_DUE -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "status", "expected"),
    [
        (6, "planned", []),
        (5, "planned", [("PAYMENT_DUE", "warning")]),
        (0, "requested", [("PAYMENT_DUE", "warning")]),
        (-2, "planned", [("PAYMENT_DUE", "warning")]),
        (1, "approved", []),
        (1, "paid", []),
        (1, "rejected", []),
    ],
)
def test_payment_due_boundaries(days: int, status: str, expected: list[tuple[str, str]]) -> None:
    out = r.payment_due(
        payment_id="x",
        package_id="p",
        package_label="G",
        due_date=TODAY + timedelta(days=days),
        status=status,
        today=TODAY,
    )
    assert _kinds(out) == expected


def test_payment_due_without_date_is_quiet() -> None:
    out = r.payment_due(
        payment_id="x",
        package_id="p",
        package_label="G",
        due_date=None,
        status="planned",
        today=TODAY,
    )
    assert out == []


# --- fingerprint and health --------------------------------------------------------------------


def test_fingerprint_is_rule_entity_level() -> None:
    c = r.Candidate("ISSUE_SLA", "warning", "issue", "abc", "t", "m", level="L2")
    assert c.fingerprint == "ISSUE_SLA:abc:L2"


def _health(
    sev: list[str], gap: str = "0", *, status: str = "executing", contract: bool = True
) -> r.Health:
    return r.package_health(status=status, has_contract=contract, open_severities=sev, gap=D(gap))


def test_health_levels() -> None:
    assert _health(["critical", "warning"]).value == "red"
    assert _health([], "26").value == "red"
    assert _health([], "25").value == "amber"
    assert _health(["warning"]).value == "amber"
    assert _health([], "11").value == "amber"
    assert _health([], "10").value == "green"
    assert _health(["info"]).value == "green"


def test_health_grey_for_unstarted_or_closed_with_reason() -> None:
    no_contract = _health(["critical"], contract=False, status="planning")
    assert (no_contract.value, no_contract.reason) == ("grey", "Chưa có hợp đồng")
    assert _health([], status="settled").value == "grey"
    assert _health(["critical"], status="cancelled").value == "grey"
    assert "2 cảnh báo nghiêm trọng" in _health(["critical", "critical"]).reason
