"""SPEC 4.4 progress rules: ok / boundary / violation for each."""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.services.progress import (
    DEFAULT_WEIGHTS,
    STAGE_ORDER,
    StageFacts,
    all_tasks_done,
    current_stage,
    effective_stage_status,
    package_progress,
    stage_dates_valid,
    would_create_cycle,
)

D = Decimal


def stages(progress: dict[str, int], status: dict[str, str] | None = None) -> list[StageFacts]:
    status = status or {}
    return [
        StageFacts(
            code, D(progress.get(code, 0)), DEFAULT_WEIGHTS[code], status.get(code, "not_started")
        )
        for code in STAGE_ORDER
    ]


def test_default_weights_follow_the_spec() -> None:
    assert [DEFAULT_WEIGHTS[c] for c in STAGE_ORDER] == [10, 20, 40, 20, 10]
    assert sum(DEFAULT_WEIGHTS.values()) == 100


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        ({}, "0.00"),
        ({"S1_START": 100}, "10.00"),
        ({"S1_START": 100, "S2_SELECTION": 100}, "30.00"),
        ({"S3_EXECUTION": 50}, "20.00"),
        ({c: 100 for c in STAGE_ORDER}, "100.00"),
        ({"S2_SELECTION": 33, "S3_EXECUTION": 17}, "13.40"),  # (33*20 + 17*40) / 100
    ],
)
def test_package_progress_is_the_weighted_average(progress: dict[str, int], expected: str) -> None:
    assert package_progress(stages(progress)) == D(expected)


def test_progress_with_custom_weights_is_normalised_by_their_sum() -> None:
    items = [
        StageFacts("S1_START", D(100), D(1), "done"),
        StageFacts("S2_SELECTION", D(0), D(3), "not_started"),
    ]
    assert package_progress(items) == D("25.00")


def test_progress_is_zero_when_no_stage_has_weight() -> None:
    assert package_progress([StageFacts("S1_START", D(100), D(0), "done")]) == D(0)
    assert package_progress([]) == D(0)


def test_progress_is_rounded_to_two_places() -> None:
    items = [StageFacts("S1_START", D(1), D(1), "x"), StageFacts("S2_SELECTION", D(0), D(2), "x")]
    assert package_progress(items) == D("0.33")


def test_current_stage_is_the_first_unfinished_one() -> None:
    assert current_stage(stages({}, {})) == "S1_START"
    done = {"S1_START": "done", "S2_SELECTION": "done"}
    assert current_stage(stages({}, done)) == "S3_EXECUTION"
    # a later stage already done does not skip an earlier unfinished one
    assert current_stage(stages({}, {"S3_EXECUTION": "done"})) == "S1_START"
    assert current_stage(stages({}, {c: "done" for c in STAGE_ORDER})) == "S5_PAYMENT_SETTLEMENT"


TODAY = date(2026, 10, 6)


@pytest.mark.parametrize(
    ("status", "planned_end", "progress", "expected"),
    [
        ("in_progress", date(2026, 10, 5), 50, "delayed"),  # one day late
        ("in_progress", date(2026, 10, 6), 50, "in_progress"),  # boundary: ends today is not late
        ("in_progress", date(2026, 10, 7), 50, "in_progress"),
        ("not_started", date(2026, 9, 1), 0, "delayed"),
        ("done", date(2026, 9, 1), 100, "done"),
        ("blocked", date(2026, 9, 1), 10, "blocked"),
        ("in_progress", None, 10, "in_progress"),  # no plan, nothing to be late against
        (
            "in_progress",
            date(2026, 9, 1),
            100,
            "in_progress",
        ),  # fully progressed but not marked done
    ],
)
def test_effective_stage_status(
    status: str, planned_end: date | None, progress: int, expected: str
) -> None:
    assert effective_stage_status(status, planned_end, D(progress), TODAY) == expected


def test_stage_dates_must_not_run_backwards() -> None:
    d = date
    assert stage_dates_valid(d(2026, 1, 1), d(2026, 1, 1), None, None) == []  # same day is fine
    assert stage_dates_valid(d(2026, 1, 2), d(2026, 1, 1), None, None) == ["planned_end"]
    assert stage_dates_valid(None, d(2026, 1, 1), None, None) == []
    assert stage_dates_valid(d(2026, 1, 2), d(2026, 1, 1), d(2026, 2, 2), d(2026, 2, 1)) == [
        "planned_end",
        "actual_end",
    ]


def ids(n: int) -> list[uuid.UUID]:
    return [uuid.UUID(int=i + 1) for i in range(n)]


def test_dependency_cycles_are_detected() -> None:
    a, b, c = ids(3)
    edges = {a: [b], b: [c], c: []}
    assert not would_create_cycle(edges, c, [])  # no deps
    assert would_create_cycle(edges, c, [a])  # c -> a -> b -> c
    assert would_create_cycle(edges, a, [a])  # itself
    assert would_create_cycle(edges, b, [a])  # b -> a -> b
    assert not would_create_cycle(edges, a, [c])  # a -> c, a -> b -> c: a diamond is fine
    assert not would_create_cycle({}, a, [b])  # unknown tasks have no edges


def test_stage_completion_suggestion_needs_at_least_one_task_and_all_done() -> None:
    assert all_tasks_done(["done", "done"])
    assert not all_tasks_done(["done", "doing"])
    assert not all_tasks_done([])
    assert not all_tasks_done(["blocked"])
