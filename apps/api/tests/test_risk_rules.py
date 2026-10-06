"""SPEC 4.8 / 4.9 / 7.4 rules: ok / boundary / violation for each."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.risk_rules import (
    add_working_days,
    compute_due_at,
    is_overdue,
    is_working_day,
    matrix_counts,
    overdue_days,
    risk_level,
    risk_needs_review,
    risk_score,
)

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def vn(y: int, m: int, d: int, h: int = 10, minute: int = 0) -> datetime:
    return datetime(y, m, d, h, minute, tzinfo=VN).astimezone(UTC)


# --- risks ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("p", "i", "score"), [(1, 1, 1), (5, 5, 25), (3, 4, 12), (2, 3, 6)])
def test_score_is_probability_times_impact(p: int, i: int, score: int) -> None:
    assert risk_score(p, i) == score


@pytest.mark.parametrize(
    ("score", "level"),
    [(1, "low"), (5, "low"), (6, "medium"), (12, "medium"), (13, "high"), (25, "high")],
)
def test_level_boundaries_follow_the_spec(score: int, level: str) -> None:
    assert risk_level(score) == level


def test_matrix_has_all_25_cells_and_counts_risks() -> None:
    grid = matrix_counts([(5, 4), (5, 4), (1, 1)])
    assert len(grid) == 25
    assert grid[(5, 4)] == 2 and grid[(1, 1)] == 1 and grid[(3, 3)] == 0
    assert sum(grid.values()) == 3
    assert matrix_counts([]) == {(p, i): 0 for p in range(1, 6) for i in range(1, 6)}


NOW = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("status", "created_days_ago", "reviewed_days_ago", "expected"),
    [
        ("open", 15, None, True),  # never reviewed, older than 14 days
        ("open", 14, None, False),  # boundary: exactly 14 days is still fine
        ("open", 30, 3, False),  # reviewed recently
        ("open", 30, 15, True),  # last review too old
        ("mitigating", 60, None, False),  # only `open` risks are chased
        ("closed", 60, None, False),
    ],
)
def test_review_reminder(
    status: str, created_days_ago: int, reviewed_days_ago: int | None, expected: bool
) -> None:
    created = NOW - timedelta(days=created_days_ago)
    reviewed = NOW - timedelta(days=reviewed_days_ago) if reviewed_days_ago is not None else None
    assert risk_needs_review(status, created, reviewed, NOW) is expected


# --- working days -----------------------------------------------------------------------------


def test_working_days_skip_weekends_and_holidays() -> None:
    assert is_working_day(date(2026, 10, 9), set())  # Friday
    assert not is_working_day(date(2026, 10, 10), set())  # Saturday
    assert not is_working_day(date(2026, 10, 11), set())  # Sunday
    assert not is_working_day(date(2026, 10, 12), {date(2026, 10, 12)})  # Monday holiday


@pytest.mark.parametrize(
    ("start", "n", "holidays", "expected"),
    [
        (date(2026, 10, 8), 3, [], date(2026, 10, 13)),  # Thu -> Fri, Mon, Tue
        (date(2026, 10, 9), 1, [], date(2026, 10, 12)),  # Fri + 1 = Mon
        (date(2026, 10, 10), 3, [], date(2026, 10, 14)),  # Saturday: counting starts Monday
        (date(2026, 10, 11), 1, [], date(2026, 10, 12)),  # Sunday + 1 = Monday
        (date(2026, 10, 8), 3, [date(2026, 10, 12)], date(2026, 10, 14)),  # Monday off
        (date(2026, 10, 8), 3, [date(2026, 10, 9), date(2026, 10, 12)], date(2026, 10, 15)),
        (date(2026, 10, 8), 0, [], date(2026, 10, 8)),
    ],
)
def test_add_working_days(start: date, n: int, holidays: list[date], expected: date) -> None:
    assert add_working_days(start, n, set(holidays)) == expected


# --- issue deadlines --------------------------------------------------------------------------


def test_level_1_is_two_calendar_days_after_creation() -> None:
    due = compute_due_at(1, "operational", vn(2026, 10, 9, 14, 30), set(), VN)
    assert due == vn(2026, 10, 11, 14, 30)  # a Sunday: level 1 counts calendar days


def test_level_2_is_three_working_days_after_escalation_keeping_the_time_of_day() -> None:
    due = compute_due_at(2, "contract", vn(2026, 10, 8, 16, 45), set(), VN)  # Thursday
    assert due == vn(2026, 10, 13, 16, 45)  # Tuesday
    with_holiday = compute_due_at(2, "contract", vn(2026, 10, 8, 16, 45), {date(2026, 10, 12)}, VN)
    assert with_holiday == vn(2026, 10, 14, 16, 45)


def test_level_2_uses_the_vietnam_date_not_utc() -> None:
    # 23:30 Thursday in Vietnam is 16:30 UTC the same day; 01:00 Friday in VN is Thursday UTC.
    friday_early = vn(2026, 10, 9, 1, 0)
    assert friday_early.date() == date(2026, 10, 8)  # UTC date differs from the local one
    due = compute_due_at(2, "contract", friday_early, set(), VN)
    assert due == vn(2026, 10, 14, 1, 0)  # Fri + 3 working days = Wed, not Tue


def test_level_3_has_no_automatic_deadline() -> None:
    assert compute_due_at(3, "schedule", vn(2026, 10, 8), set(), VN) is None


@pytest.mark.parametrize("level", [1, 2, 3])
def test_investor_requests_are_due_in_one_day_including_weekends(level: int) -> None:
    friday = vn(2026, 10, 9, 17, 0)
    assert compute_due_at(level, "investor_request", friday, set(), VN) == vn(2026, 10, 10, 17, 0)


def test_overdue_boundaries() -> None:
    due = datetime(2026, 10, 10, 8, 0, tzinfo=UTC)
    assert not is_overdue(due, "open", due)  # exactly at the deadline is still on time
    assert is_overdue(due, "open", due + timedelta(seconds=1))
    assert not is_overdue(None, "open", due)
    assert not is_overdue(due, "resolved", due + timedelta(days=5))
    assert not is_overdue(due, "closed", due + timedelta(days=5))
    assert overdue_days(due, "open", due + timedelta(hours=23)) == 0
    assert overdue_days(due, "open", due + timedelta(days=1)) == 1  # ISSUE_SLA turns critical here
    assert overdue_days(due, "open", due + timedelta(days=3, hours=2)) == 3
    assert overdue_days(due, "resolved", due + timedelta(days=9)) == 0
    assert overdue_days(None, "open", due) == 0
