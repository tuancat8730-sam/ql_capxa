"""Load the SGD-HCM construction logs (`sgd_hcm_logs_data`) into the database.

`apply_logs` is plain SQL on a connection so migration 0017 (an existing database) and the seed
(a new one) share it. It only adds the weeks that have no log yet: a log someone has edited or
written in the application is never overwritten, and running it twice changes nothing.
"""

import json
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed import sgd_hcm_logs_data as data
from app.seed.sgd_hcm_progress import PROJECT_CODE


def _date(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None


def _project_id(bind: sa.Connection) -> object | None:
    return bind.execute(
        sa.text("SELECT id FROM projects WHERE code = :code AND deleted_at IS NULL"),
        {"code": PROJECT_CODE},
    ).scalar()


def _insert_log(bind: sa.Connection, project_id: object, log: dict[str, Any]) -> object:
    return bind.execute(
        sa.text(
            "INSERT INTO construction_logs (id, project_id, week_start, report_date, recipients, "
            "reporter_org, contract_ref, coordinator, environment_note, overall_status, "
            "key_results, issues, coordination_requests, related_report) "
            "VALUES (gen_random_uuid(), :p, :week, :report, :recipients, :reporter, :contract, "
            ":coordinator, :environment, :status, :results, :issues, :requests, :related) "
            "RETURNING id"
        ),
        {
            "p": project_id,
            "week": _date(log["week_start"]),
            "report": _date(log["report_date"]),
            "recipients": log["recipients"],
            "reporter": log["reporter_org"],
            "contract": log["contract_ref"],
            "coordinator": log["coordinator"],
            "environment": log["environment_note"],
            "status": log["overall_status"],
            "results": log["key_results"],
            "issues": log["issues"],
            "requests": log["coordination_requests"],
            "related": log["related_report"],
        },
    ).scalar_one()


def _insert_children(bind: sa.Connection, log_id: object, log: dict[str, Any]) -> None:
    if log["entries"]:
        bind.execute(
            sa.text(
                "INSERT INTO construction_log_entries (id, log_id, entry_date, seq, phase_code, "
                "task_code, content, personnel, note, state, delay_days) VALUES "
                "(gen_random_uuid(), :log, :day, :seq, :phase, :task, :content, "
                "CAST(:personnel AS jsonb), :note, :state, :delay)"
            ),
            [
                {
                    "log": log_id,
                    "day": _date(day),
                    "seq": seq,
                    "phase": phase,
                    "task": task,
                    "content": content,
                    "personnel": json.dumps(personnel, ensure_ascii=False),
                    "note": note,
                    "state": state,
                    "delay": delay,
                }
                for seq, (day, phase, task, content, personnel, note, state, delay) in enumerate(
                    log["entries"]
                )
            ],
        )
    if log["carryovers"]:
        bind.execute(
            sa.text(
                "INSERT INTO construction_log_carryovers (id, log_id, seq, phase_code, task_code, "
                "title, result_to_date, next_week, note) VALUES "
                "(gen_random_uuid(), :log, :seq, :phase, :task, :title, :result, :next, :note)"
            ),
            [
                {
                    "log": log_id,
                    "seq": seq,
                    "phase": phase,
                    "task": task,
                    "title": title,
                    "result": result,
                    "next": next_week,
                    "note": note,
                }
                for seq, (phase, task, title, result, next_week, note) in enumerate(
                    log["carryovers"]
                )
            ],
        )
    if log["member_work"]:
        bind.execute(
            sa.text(
                "INSERT INTO construction_log_member_work (id, log_id, seq, member_name, item, "
                "plan_ref, personnel, result, next_plan, issues_actions) VALUES "
                "(gen_random_uuid(), :log, :seq, :member, :item, :plan, CAST(:personnel AS jsonb), "
                ":result, :next, :issues)"
            ),
            [
                {
                    "log": log_id,
                    "seq": seq,
                    "member": m["member_name"],
                    "item": m["item"],
                    "plan": m["plan_ref"],
                    "personnel": json.dumps(m["personnel"], ensure_ascii=False),
                    "result": m["result"],
                    "next": m["next_plan"],
                    "issues": m["issues_actions"],
                }
                for seq, m in enumerate(log["member_work"])
            ],
        )


def apply_logs(bind: sa.Connection) -> int:
    """Add the logs of the weeks that have none; returns how many were added."""
    project_id = _project_id(bind)
    if project_id is None:
        return 0
    added = 0
    for log in data.LOGS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM construction_logs WHERE project_id = :p AND week_start = :week"),
            {"p": project_id, "week": _date(log["week_start"])},
        ).first()
        if exists:
            continue
        _insert_children(bind, _insert_log(bind, project_id, log), log)
        added += 1
    return added


async def seed_sgd_hcm_logs(session: AsyncSession) -> None:
    def run(sync_session: sa.orm.Session) -> None:
        apply_logs(sync_session.connection())

    await session.run_sync(run)
    await session.commit()
