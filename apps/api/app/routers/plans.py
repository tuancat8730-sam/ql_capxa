"""Delivery plan of a package (tab "Kế hoạch"): read, upload a plan document, track the steps."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import PackagePlan, PlanStep, User
from app.routers.packages import package_or_404
from app.schemas.plan import (
    ImportPreview,
    PlanOut,
    PlanStepOut,
    PreviewItem,
    PreviewStep,
    StepUpdate,
)
from app.services import audit
from app.services.finance import today_local
from app.services.plan_parser import Finding, ParsedPlan, parse_plan, plan_findings
from app.services.plan_reader import MAX_BYTES, PlanFileError, read_plan_document
from app.services.plans import (
    effective_step_status,
    finding_out,
    load_plan,
    match_tracking,
    package_contract_end,
    present,
    save_plan,
)

router = APIRouter(tags=["plans"])

Reader = Annotated[User, Depends(require("package", Level.READ))]
# who may upload or delete a plan: admin, director, procurement (SPEC section 8 "package" write)
Uploader = Annotated[User, Depends(require("package", Level.WRITE))]
# who may update the execution of a step: admin, director, technical, site engineer ("progress")
Tracker = Annotated[User, Depends(require("progress", Level.WRITE))]

_STEP_TRACKED = ("status", "actual_start", "actual_end", "tracking_note")


async def _plan_out(session: AsyncSession, package_id: uuid.UUID) -> PlanOut | None:
    loaded = await load_plan(session, package_id)
    if loaded is None:
        return None
    plan, items, steps = loaded
    contract_end = await package_contract_end(session, package_id)
    return present(plan, items, steps, contract_end, today_local())


@router.get("/packages/{package_id}/plan", response_model=PlanOut | None)
async def read_plan(package_id: uuid.UUID, _: Reader, session: SessionDep) -> PlanOut | None:
    """The package's plan, or null while it has none."""
    await package_or_404(session, package_id)
    return await _plan_out(session, package_id)


def _preview(
    parsed: ParsedPlan,
    *,
    findings: list[Finding],
    replaces: bool,
    kept_hashes: set[int],
    dry_run: bool,
    plan_id: uuid.UUID | None,
) -> ImportPreview:
    return ImportPreview(
        dry_run=dry_run,
        replaces_existing=replaces,
        addressee=parsed.addressee,
        contract_start=parsed.contract_start,
        contract_end=parsed.contract_end,
        implement_start=parsed.implement_start,
        implement_end=parsed.implement_end,
        locations=len(parsed.locations),
        total_quantity=sum(i.quantity or 0 for i in parsed.items),
        items=[
            PreviewItem(
                line_no=i.line_no, name=i.name, quantity=i.quantity, assignments=i.assignments
            )
            for i in parsed.items
        ],
        steps=[
            PreviewStep(
                step_no=s.step_no,
                group_no=s.group_no,
                group_title=s.group_title,
                summary=s.content.split("\n")[0][:200],
                start_date=s.start_date,
                end_date=s.end_date,
                estimated=s.estimated,
                keeps_tracking=index in kept_hashes,
            )
            for index, s in enumerate(parsed.steps)
        ],
        kept_tracking=len(kept_hashes),
        findings=[finding_out(f) for f in findings],
        plan_id=plan_id,
    )


@router.post("/packages/{package_id}/plan/import", response_model=ImportPreview)
async def import_plan(
    package_id: uuid.UUID,
    request: Request,
    user: Uploader,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    commit: Annotated[bool, Query()] = False,
) -> ImportPreview:
    """Read a plan document (.docx or .doc). Without `commit` nothing is saved: the result is the
    preview. With `commit=true` the plan is created, or replaces the current one while the steps
    whose wording did not change keep their tracking."""
    package = await package_or_404(session, package_id)
    content = await file.read(MAX_BYTES + 1)
    try:
        parsed = parse_plan(read_plan_document(content, file.filename or ""))
    except PlanFileError as exc:
        raise AppError(422, "invalid_plan_file", str(exc), ["file"]) from exc

    existing = await load_plan(session, package_id)
    matched = match_tracking(existing[2], parsed.steps) if existing else {}
    kept_indexes = {
        i
        for i, old in matched.items()
        if old.status != "not_started" or (old.actual_start or old.actual_end or old.tracking_note)
    }
    contract_end = await package_contract_end(session, package_id)
    findings = plan_findings(parsed, contract_end=contract_end)

    plan_id: uuid.UUID | None = existing[0].id if existing else None
    kept = len(kept_indexes)
    if commit:
        plan, _kept_all, replaced = await save_plan(
            session, package, parsed, file_name=file.filename or "", user_id=user.id
        )
        plan_id = plan.id
        audit.record(
            session,
            action="update" if replaced else "create",
            entity_type="package_plan",
            entity_id=plan.id,
            user_id=user.id,
            changes={
                "file": file.filename,
                "items": len(parsed.items),
                "steps": len(parsed.steps),
                "replaced": replaced,
                "kept_tracking": kept,
                "package_id": str(package_id),
            },
            request=request,
        )
        await session.commit()
    return _preview(
        parsed,
        findings=findings,
        replaces=existing is not None,
        kept_hashes=kept_indexes,
        dry_run=not commit,
        plan_id=plan_id,
    )


@router.delete("/packages/{package_id}/plan", status_code=204)
async def delete_plan(
    package_id: uuid.UUID, request: Request, user: Uploader, session: SessionDep
) -> Response:
    await package_or_404(session, package_id)
    loaded = await load_plan(session, package_id)
    if loaded is None:
        raise AppError(404, "not_found", "Gói thầu chưa có kế hoạch")
    plan, items, steps = loaded
    audit.record(
        session,
        action="delete",
        entity_type="package_plan",
        entity_id=plan.id,
        user_id=user.id,
        changes={"items": len(items), "steps": len(steps), "package_id": str(package_id)},
        request=request,
    )
    for row in (*steps, *items, plan):
        await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.patch("/plan-steps/{step_id}", response_model=PlanStepOut)
async def update_step(
    step_id: uuid.UUID, body: StepUpdate, request: Request, user: Tracker, session: SessionDep
) -> PlanStepOut:
    """Update the execution of one step. `done` fills today's date as the actual end when none is
    given, and `in_progress` (or `done`) fills the actual start."""
    step = await session.get(PlanStep, step_id)
    if step is None:
        raise AppError(404, "not_found", "Không tìm thấy bước kế hoạch")
    plan = await session.get(PackagePlan, step.plan_id)
    if plan is None:
        raise AppError(404, "not_found", "Không tìm thấy bước kế hoạch")
    await package_or_404(session, plan.package_id)
    changes = body.model_dump(exclude_unset=True)
    before = audit.snapshot(step, _STEP_TRACKED)
    for field, value in changes.items():
        setattr(step, field, value)
    today = today_local()
    if changes.get("status") == "done" and step.actual_end is None:
        step.actual_end = today
    if changes.get("status") in {"in_progress", "done"} and step.actual_start is None:
        step.actual_start = step.actual_end or today
    if step.actual_start and step.actual_end and step.actual_end < step.actual_start:
        raise AppError(
            422, "validation_error", "Ngày kết thúc thực tế trước ngày bắt đầu", ["actual_end"]
        )
    step.updated_by = user.id
    audit.record(
        session,
        action="update",
        entity_type="plan_step",
        entity_id=step.id,
        user_id=user.id,
        changes=audit.diff(before, audit.snapshot(step, _STEP_TRACKED)),
        request=request,
    )
    await session.commit()
    out = PlanStepOut.model_validate(step)
    out.effective_status, out.days_late = effective_step_status(  # type: ignore[assignment]
        step.status, step.end_date, today
    )
    return out
