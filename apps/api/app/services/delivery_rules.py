"""Progress figures and states of a software-delivery schedule.

Pure functions over small immutable views of the data, so they are easy to test and are shared by
the overview page and the alert engine. The weight of a task in every percentage is its number of
working days; milestones weigh nothing.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

TaskState = Literal["done", "paused", "late", "stale", "todo", "behind", "progress"]

# A task counts as behind once it is this many points under where the plan says it should be.
BEHIND_MARGIN = 25
REPORT_DAYS = 7


@dataclass(frozen=True)
class TaskView:
    code: str
    phase_code: str
    is_milestone: bool
    plan_start: date
    plan_end: date
    plan_days: int
    tracked: bool
    status: str
    pct: int


@dataclass(frozen=True)
class Week:
    no: int
    start: date
    end: date


def working_days(first: date, last: date) -> int:
    """Monday-to-Friday days in [first, last], both included (0 when the range is empty)."""
    if last < first:
        return 0
    days = (first + timedelta(days=i) for i in range((last - first).days + 1))
    return sum(1 for d in days if d.weekday() < 5)


def task_pct(task: TaskView) -> int:
    """Completion of one line: a milestone is all or nothing."""
    if task.is_milestone:
        return 100 if task.tracked and task.status == "done" else 0
    return max(0, min(100, task.pct)) if task.tracked else 0


def plan_fraction(task: TaskView, at: date) -> float:
    """Share of the task the plan expects to be done at the end of day `at` (0..1)."""
    span = (task.plan_end - task.plan_start).days + 1
    return max(0.0, min(1.0, ((at - task.plan_start).days + 1) / span))


def plan_pct_at(tasks: Iterable[TaskView], at: date) -> float:
    weight = done = 0.0
    for t in tasks:
        if t.is_milestone:
            continue
        weight += t.plan_days
        done += t.plan_days * plan_fraction(t, at)
    return done / weight * 100 if weight else 0.0


def actual_pct(tasks: Iterable[TaskView]) -> float:
    weight = done = 0.0
    for t in tasks:
        if t.is_milestone:
            continue
        weight += t.plan_days
        done += t.plan_days * task_pct(t)
    return done / weight if weight else 0.0


def task_state(task: TaskView, today: date) -> TaskState:
    pct = task_pct(task)
    if task.tracked and (task.status == "done" or pct >= 100):
        return "done"
    if task.tracked and task.status == "on_hold":
        return "paused"
    if task.is_milestone:
        return ("late" if task.tracked else "stale") if today > task.plan_start else "todo"
    if today > task.plan_end:
        return "late" if task.tracked else "stale"
    if today < task.plan_start:
        return "todo"
    if not task.tracked:
        return "stale"
    return "behind" if pct < plan_fraction(task, today) * 100 - BEHIND_MARGIN else "progress"


def late_days(task: TaskView, today: date) -> int:
    """Working days past the planned end."""
    return working_days(task.plan_end + timedelta(days=1), today) if today > task.plan_end else 0


def phase_state(states: Sequence[TaskState], phase_start: date, today: date) -> TaskState:
    if all(s == "done" for s in states):
        return "done"
    for worst in ("late", "behind", "stale"):
        if worst in states:
            return worst
    if "progress" in states or "done" in states:
        return "progress"
    return "stale" if today >= phase_start else "todo"


def report_weeks(first_day: date, last_day: date) -> list[Week]:
    """The 7-day reporting periods that cover the project, numbered from 1."""
    weeks: list[Week] = []
    start = first_day
    while start <= last_day:
        weeks.append(Week(len(weeks) + 1, start, start + timedelta(days=REPORT_DAYS - 1)))
        start += timedelta(days=REPORT_DAYS)
    return weeks


def normalise_update(
    *,
    is_milestone: bool,
    plan_start: date,
    plan_end: date,
    status: str,
    pct: int,
    actual_start: date | None,
    actual_end: date | None,
    today: date,
) -> tuple[str, int, date | None, date | None]:
    """Make a progress entry consistent, the way the site manager expects it to behave.

    Finished means 100% and has an end date; 100% means finished; any progress on a task that has
    not started means it is under way; a task under way or done has a start date.
    """
    if is_milestone:
        if status == "done" and actual_end is None:
            actual_end = today
        return status, 0, actual_start, actual_end
    if status == "done":
        pct = 100
        actual_end = actual_end or today
    elif pct >= 100:
        status = "done"
        actual_end = actual_end or today
    elif pct > 0 and status == "not_started":
        status = "in_progress"
    if status in {"in_progress", "done"} and actual_start is None:
        actual_start = max(plan_start, min(today, plan_end))
    return status, max(0, min(100, pct)), actual_start, actual_end
