"""Progress figures of a software-delivery schedule (the rules behind the SGD-HCM page)."""

from datetime import date

import pytest

from app.services.delivery_rules import (
    TaskView,
    actual_pct,
    late_days,
    normalise_update,
    phase_state,
    plan_fraction,
    plan_pct_at,
    report_weeks,
    task_pct,
    task_state,
    working_days,
)


def task(
    start: str = "2026-10-05",
    end: str = "2026-10-09",
    *,
    days: int = 5,
    tracked: bool = False,
    status: str = "not_started",
    pct: int = 0,
    milestone: bool = False,
    code: str = "T-1",
) -> TaskView:
    return TaskView(
        code=code,
        phase_code="I",
        is_milestone=milestone,
        plan_start=date.fromisoformat(start),
        plan_end=date.fromisoformat(end),
        plan_days=0 if milestone else days,
        tracked=tracked,
        status=status,
        pct=pct,
    )


def d(iso: str) -> date:
    return date.fromisoformat(iso)


def test_working_days_skip_weekends() -> None:
    assert working_days(d("2026-10-05"), d("2026-10-09")) == 5  # Mon-Fri
    assert working_days(d("2026-10-05"), d("2026-10-11")) == 5  # ... through Sunday
    assert working_days(d("2026-10-10"), d("2026-10-11")) == 0  # a weekend
    assert working_days(d("2026-10-09"), d("2026-10-05")) == 0  # empty range


def test_plan_fraction_runs_from_start_of_the_first_day_to_end_of_the_last() -> None:
    t = task("2026-10-05", "2026-10-09")
    assert plan_fraction(t, d("2026-10-04")) == 0
    assert plan_fraction(t, d("2026-10-05")) == pytest.approx(0.2)
    assert plan_fraction(t, d("2026-10-09")) == 1
    assert plan_fraction(t, d("2026-12-01")) == 1


def test_untracked_lines_count_as_zero_percent() -> None:
    assert task_pct(task(pct=80)) == 0
    assert task_pct(task(tracked=True, pct=80)) == 80
    assert task_pct(task(tracked=True, pct=180)) == 100


def test_a_milestone_is_all_or_nothing() -> None:
    assert task_pct(task(milestone=True, tracked=True, status="done")) == 100
    assert task_pct(task(milestone=True, tracked=True, status="in_progress", pct=60)) == 0


def test_figures_are_weighted_by_working_days_and_ignore_milestones() -> None:
    long = task("2026-10-05", "2026-10-16", days=10, tracked=True, status="done", pct=100)
    short = task("2026-10-05", "2026-10-09", days=5, code="T-2")
    ms = task("2026-10-09", "2026-10-09", milestone=True, code="M1")
    assert actual_pct([long, short, ms]) == pytest.approx(10 / 15 * 100)
    # on 9 Oct: 5 of the long task's 12 calendar days have passed; the short one is fully planned
    expected = (10 * (5 / 12) + 5) / 15 * 100
    assert plan_pct_at([long, short, ms], d("2026-10-09")) == pytest.approx(expected)
    assert actual_pct([]) == 0 and plan_pct_at([ms], d("2026-10-09")) == 0


@pytest.mark.parametrize(
    ("today", "kwargs", "expected"),
    [
        ("2026-10-01", {}, "todo"),  # not started yet
        ("2026-10-06", {}, "stale"),  # in its period but nobody recorded anything
        ("2026-10-06", {"tracked": True, "status": "in_progress", "pct": 20}, "progress"),
        ("2026-10-09", {"tracked": True, "status": "in_progress", "pct": 50}, "behind"),
        ("2026-10-12", {}, "stale"),  # past its end, never updated
        ("2026-10-12", {"tracked": True, "status": "in_progress", "pct": 90}, "late"),
        ("2026-10-12", {"tracked": True, "status": "done", "pct": 100}, "done"),
        ("2026-10-12", {"tracked": True, "status": "in_progress", "pct": 100}, "done"),
        ("2026-10-06", {"tracked": True, "status": "on_hold", "pct": 10}, "paused"),
    ],
)
def test_task_state(today: str, kwargs: dict[str, object], expected: str) -> None:
    assert task_state(task(**kwargs), d(today)) == expected  # type: ignore[arg-type]


def test_a_task_is_behind_only_past_the_margin() -> None:
    # on the last day the plan wants 100%: 75% is exactly the margin, 74% is behind
    on_hold = {"tracked": True, "status": "in_progress"}
    assert task_state(task(pct=75, **on_hold), d("2026-10-09")) == "progress"  # type: ignore[arg-type]
    assert task_state(task(pct=74, **on_hold), d("2026-10-09")) == "behind"  # type: ignore[arg-type]


def test_milestone_states() -> None:
    m = task("2026-10-07", "2026-10-07", milestone=True)
    assert task_state(m, d("2026-10-07")) == "todo"  # due today: not late yet
    assert task_state(m, d("2026-10-08")) == "stale"
    tracked = task("2026-10-07", "2026-10-07", milestone=True, tracked=True, status="in_progress")
    assert task_state(tracked, d("2026-10-08")) == "late"
    done = task("2026-10-07", "2026-10-07", milestone=True, tracked=True, status="done")
    assert task_state(done, d("2026-10-08")) == "done"


def test_late_days_count_working_days_after_the_end() -> None:
    t = task("2026-10-05", "2026-10-09")
    assert late_days(t, d("2026-10-09")) == 0
    assert late_days(t, d("2026-10-12")) == 1  # Monday
    assert late_days(t, d("2026-10-11")) == 0  # weekend only
    assert late_days(t, d("2026-10-16")) == 5


def test_phase_state_takes_the_worst_task() -> None:
    start = d("2026-10-05")
    today = d("2026-10-06")
    assert phase_state(["done", "done"], start, today) == "done"
    assert phase_state(["done", "late", "todo"], start, today) == "late"
    assert phase_state(["progress", "behind"], start, today) == "behind"
    assert phase_state(["progress", "stale"], start, today) == "stale"
    assert phase_state(["progress", "todo"], start, today) == "progress"
    assert phase_state(["todo", "todo"], start, d("2026-10-01")) == "todo"
    assert phase_state(["todo", "todo"], start, today) == "stale"  # started, nothing recorded


def test_report_weeks_cover_the_project_in_seven_day_periods() -> None:
    weeks = report_weeks(d("2026-09-25"), d("2026-12-09"))
    assert len(weeks) == 11
    assert (weeks[0].no, weeks[0].start, weeks[0].end) == (1, d("2026-09-25"), d("2026-10-01"))
    assert weeks[1].start == d("2026-10-02")  # Friday to Thursday, as the contractor reports
    assert weeks[-1].end >= d("2026-12-09")


BASE = {
    "is_milestone": False,
    "plan_start": d("2026-10-05"),
    "plan_end": d("2026-10-09"),
    "actual_start": None,
    "actual_end": None,
    "today": d("2026-10-07"),
}


def run(status: str, pct: int, **over: object) -> tuple[str, int, date | None, date | None]:
    return normalise_update(**{**BASE, **over}, status=status, pct=pct)  # type: ignore[arg-type]


def test_done_means_full_and_gets_an_end_date() -> None:
    assert run("done", 40) == ("done", 100, d("2026-10-07"), d("2026-10-07"))


def test_full_means_done() -> None:
    assert run("in_progress", 100)[0] == "done"


def test_progress_on_a_task_that_has_not_started_starts_it() -> None:
    assert run("not_started", 30) == ("in_progress", 30, d("2026-10-07"), None)


def test_the_start_date_is_kept_inside_the_planned_period() -> None:
    early = run("in_progress", 10, today=d("2026-10-01"))
    late = run("in_progress", 10, today=d("2026-10-20"))
    assert early[2] == d("2026-10-05") and late[2] == d("2026-10-09")


def test_dates_that_were_typed_are_kept() -> None:
    got = run("done", 100, actual_start=d("2026-10-06"), actual_end=d("2026-10-08"))
    assert got == ("done", 100, d("2026-10-06"), d("2026-10-08"))


def test_nothing_started_stays_blank() -> None:
    assert run("not_started", 0) == ("not_started", 0, None, None)


def test_a_milestone_is_reached_on_a_day() -> None:
    got = run("done", 70, is_milestone=True)
    assert got == ("done", 0, None, d("2026-10-07"))
