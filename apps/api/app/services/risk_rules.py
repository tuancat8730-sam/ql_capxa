"""Risk and issue rules (SPEC 4.8, 4.9, 7.4): scores, matrix and working-day deadlines."""

from collections import Counter
from collections.abc import Collection, Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

RiskLevel = Literal["low", "medium", "high"]

REVIEW_AFTER_DAYS = 14  # an open risk not reviewed for this long prompts a reminder (SPEC 4.8)
LEVEL1_DAYS = 2
LEVEL2_WORKING_DAYS = 3
INVESTOR_REQUEST_DAYS = 1


def risk_score(probability: int, impact: int) -> int:
    return probability * impact


def risk_level(score: int) -> RiskLevel:
    """1-5 low, 6-12 medium, 13-25 high (SPEC 4.8)."""
    if score <= 5:
        return "low"
    return "medium" if score <= 12 else "high"


def matrix_counts(cells: Iterable[tuple[int, int]]) -> dict[tuple[int, int], int]:
    """(probability, impact) -> number of risks, for the 5x5 heat map; empty cells are 0."""
    seen = Counter(cells)
    return {(p, i): seen.get((p, i), 0) for p in range(1, 6) for i in range(1, 6)}


def risk_needs_review(
    status: str, created_at: datetime, last_reviewed_at: datetime | None, now: datetime
) -> bool:
    """Open risks nobody reviewed for more than 14 days (SPEC 4.8)."""
    if status != "open":
        return False
    since = max(created_at, last_reviewed_at) if last_reviewed_at else created_at
    return now - since > timedelta(days=REVIEW_AFTER_DAYS)


# --- issue deadlines (SPEC 7.4) -----------------------------------------------------------------


def is_working_day(day: date, holidays: Collection[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def add_working_days(start: date, n: int, holidays: Collection[date]) -> date:
    """`n` working days after `start`: Saturdays, Sundays and configured holidays do not count."""
    day = start
    remaining = n
    while remaining > 0:
        day += timedelta(days=1)
        if is_working_day(day, holidays):
            remaining -= 1
    return day


def compute_due_at(
    level: int,
    issue_type: str,
    base: datetime,
    holidays: Collection[date],
    tz: ZoneInfo,
) -> datetime | None:
    """Deadline for an issue, or None when it must be entered by hand (level 3).

    * investor request: 1 calendar day (Saturdays and Sundays included)
    * level 1: created + 2 days
    * level 2: escalation date + 3 working days
    * level 3: set manually
    `base` is the creation time (level 1) or the escalation time (level 2).
    """
    local = base.astimezone(tz)
    if issue_type == "investor_request":
        return (local + timedelta(days=INVESTOR_REQUEST_DAYS)).astimezone(UTC)
    if level == 1:
        return (local + timedelta(days=LEVEL1_DAYS)).astimezone(UTC)
    if level == 2:
        due_day = add_working_days(local.date(), LEVEL2_WORKING_DAYS, holidays)
        return datetime.combine(due_day, local.timetz().replace(tzinfo=None), tzinfo=tz).astimezone(
            UTC
        )
    return None


def overdue_days(due_at: datetime | None, status: str, now: datetime) -> int:
    """Whole days past the deadline for an unresolved issue (0 within the first 24 hours)."""
    if due_at is None or status in {"resolved", "closed"} or now <= due_at:
        return 0
    return (now - due_at).days


def is_overdue(due_at: datetime | None, status: str, now: datetime) -> bool:
    return due_at is not None and status not in {"resolved", "closed"} and now > due_at
