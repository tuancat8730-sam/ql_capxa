"""Load the SGD-HCM progress export (`sgd_hcm_data`) into the database.

`apply_progress` is plain SQL on a connection so migration 0015 (an existing database) and the
seed (a new one) share it. It upserts by natural key, so running it twice changes nothing; the
open decisions keep their status, decision and date if someone already settled them.
"""

import json
from datetime import date

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed import sgd_hcm_data as data

PROJECT_CODE = "SGD-HCM"


def _date(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None


def _project_id(bind: sa.Connection) -> object | None:
    return bind.execute(
        sa.text("SELECT id FROM projects WHERE code = :code AND deleted_at IS NULL"),
        {"code": PROJECT_CODE},
    ).scalar()


def _apply_tasks(bind: sa.Connection, project_id: object) -> None:
    for code, status, pct, started, ended, note in data.TASKS:
        bind.execute(
            sa.text(
                "UPDATE wbs_tasks SET tracked = true, status = :status, pct = :pct, "
                "actual_start = :started, actual_end = :ended, note = :note "
                "WHERE project_id = :p AND code = :code"
            ),
            {
                "status": status,
                "pct": pct,
                "started": _date(started),
                "ended": _date(ended),
                "note": note,
                "p": project_id,
                "code": code,
            },
        )


def _apply_risks(bind: sa.Connection, project_id: object) -> dict[str, str]:
    """Upsert the register; returns code -> id for the reports to point at."""
    for r in data.RISKS:
        bind.execute(
            sa.text(
                "INSERT INTO risks (id, code, project_id, title, category, probability, impact, "
                "score, mitigation, group_name, owner_text, note, status, due_date, source) "
                "VALUES (gen_random_uuid(), :code, :p, :title, 'other', :prob, :impact, :score, "
                ":mitigation, :group, :owner, :note, :status, :due, 'manual') "
                "ON CONFLICT (project_id, code) DO UPDATE SET title = :title, "
                "probability = :prob, impact = :impact, score = :score, mitigation = :mitigation, "
                "group_name = :group, owner_text = :owner, note = :note, status = :status, "
                "due_date = :due, updated_at = now()"
            ),
            {
                "code": r["code"],
                "p": project_id,
                "title": r["title"],
                "prob": r["probability"],
                "impact": r["impact"],
                "score": r["probability"] * r["impact"],
                "mitigation": r["mitigation"],
                "group": r["group_name"],
                "owner": r["owner_text"],
                "note": r["note"],
                "status": r["status"],
                "due": _date(r["due_date"]),
            },
        )
    rows = bind.execute(
        sa.text("SELECT code, id FROM risks WHERE project_id = :p"), {"p": project_id}
    )
    return {code: str(risk_id) for code, risk_id in rows}


def _apply_reports(bind: sa.Connection, project_id: object, risk_ids: dict[str, str]) -> None:
    for r in data.REPORTS:
        bind.execute(
            sa.text(
                "INSERT INTO weekly_reports (id, project_id, week_start, report_no, status, "
                "submitted_on, link, planned_pct, actual_pct, done, issues, recommendations, "
                "next_plan, risk_ids) VALUES (gen_random_uuid(), :p, :week, :no, 'received', "
                ":recv, :link, :plan, :actual, :done, :issues, :rec, :next, CAST(:risks AS jsonb)) "
                "ON CONFLICT (project_id, week_start) DO UPDATE SET report_no = :no, "
                "status = 'received', submitted_on = :recv, link = :link, planned_pct = :plan, "
                "actual_pct = :actual, done = :done, issues = :issues, recommendations = :rec, "
                "next_plan = :next, risk_ids = CAST(:risks AS jsonb), updated_at = now()"
            ),
            {
                "p": project_id,
                "week": _date(r["week_start"]),
                "no": r["report_no"],
                "recv": _date(r["submitted_on"]),
                "link": r["link"],
                "plan": r["planned_pct"],
                "actual": r["actual_pct"],
                "done": r["done"],
                "issues": r["issues"],
                "rec": r["recommendations"],
                "next": r["next_plan"],
                "risks": json.dumps([risk_ids[c] for c in r["risks"] if c in risk_ids]),
            },
        )


def _apply_decisions(bind: sa.Connection, project_id: object) -> None:
    for no, title, reason, due in data.DECISIONS:
        bind.execute(
            sa.text(
                "INSERT INTO decision_items (id, project_id, no, title, reason, status, due_date) "
                "VALUES (gen_random_uuid(), :p, :no, :title, :reason, 'pending', :due) "
                "ON CONFLICT (project_id, no) DO UPDATE SET title = :title, reason = :reason, "
                "due_date = :due, updated_at = now()"
            ),
            {"p": project_id, "no": no, "title": title, "reason": reason, "due": _date(due)},
        )


def apply_progress(bind: sa.Connection) -> bool:
    """Write the export into the SGD-HCM project; False when the project does not exist yet."""
    project_id = _project_id(bind)
    if project_id is None:
        return False
    _apply_tasks(bind, project_id)
    risk_ids = _apply_risks(bind, project_id)
    _apply_reports(bind, project_id, risk_ids)
    _apply_decisions(bind, project_id)
    return True


def _is_untouched(bind: sa.Connection) -> bool:
    """True when nobody has entered progress, reports, risks or decisions in the app yet."""
    project_id = _project_id(bind)
    if project_id is None:
        return False
    entered = bind.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM wbs_tasks WHERE project_id = :p AND tracked) "
            "+ (SELECT count(*) FROM weekly_reports WHERE project_id = :p) "
            "+ (SELECT count(*) FROM decision_items WHERE project_id = :p) "
            "+ (SELECT count(*) FROM risks WHERE project_id = :p)"
        ),
        {"p": project_id},
    ).scalar()
    return not entered


async def seed_sgd_hcm_progress(session: AsyncSession) -> None:
    """A new database gets the export once; an existing one is never overwritten by a seed run."""

    def run(sync_session: sa.orm.Session) -> None:
        bind = sync_session.connection()
        if _is_untouched(bind):
            apply_progress(bind)

    await session.run_sync(run)
    await session.commit()
