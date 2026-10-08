import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ProjectDep, SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level, can
from app.core.scope import current_project_id
from app.models import (
    Contract,
    DisbursementPlan,
    Guarantee,
    Organization,
    Package,
    Payment,
    User,
)
from app.routers.contracts import contract_or_404
from app.schemas.common import Page, PaginationDep
from app.schemas.finance import (
    DisbursementItem,
    DisbursementPlanIn,
    DisbursementPlanOut,
    FindingOut,
    GuaranteeIn,
    GuaranteeOut,
    GuaranteeRow,
    GuaranteeUpdate,
    MarkPaid,
    PaymentIn,
    PaymentOut,
    PaymentRow,
    PaymentUpdate,
)
from app.services import audit
from app.services.finance import (
    APPROVAL_TARGETS,
    PAYMENT_TRANSITIONS,
    days_left,
    effective_status,
    guarantee_findings,
    today_local,
)
from app.services.guarantee_rules import Finding

router = APIRouter(tags=["finance"])

ContractReader = Annotated[User, Depends(require("contract", Level.READ))]
ContractWriter = Annotated[User, Depends(require("contract", Level.WRITE))]
PaymentReader = Annotated[User, Depends(require("payment", Level.READ))]
PaymentWriter = Annotated[User, Depends(require("payment", Level.WRITE))]

_G_NON_NULL = frozenset({"guarantee_type", "status", "required", "verified"})
_P_NON_NULL = frozenset({"seq", "amount", "status"})


def _finding_out(f: Finding) -> FindingOut:
    return FindingOut(**f.__dict__)


def _guarantee_out(g: Guarantee, today: date, findings: list[Finding]) -> GuaranteeOut:
    out = GuaranteeOut.model_validate(g)
    out.effective_status = effective_status(g, today)  # type: ignore[assignment]
    out.days_left = days_left(g.expiry_date, today)
    out.findings = [_finding_out(f) for f in findings if f.guarantee_id == str(g.id)]
    return out


def _reject_nulls(changes: dict[str, Any], required: frozenset[str]) -> None:
    nulls = sorted(k for k, v in changes.items() if v is None and k in required)
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)


async def _require_org(session: AsyncSession, org_id: uuid.UUID | None) -> None:
    if org_id is not None and await session.get(Organization, org_id) is None:
        raise AppError(422, "validation_error", "Tổ chức không tồn tại", ["organization_id"])


def _audit(
    session: AsyncSession,
    user: User,
    request: Request,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any],
) -> None:
    audit.record(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user.id,
        changes=changes,
        request=request,
    )


# --- guarantees ------------------------------------------------------------------------------


async def _guarantees_of(session: AsyncSession, contract_id: uuid.UUID) -> list[Guarantee]:
    return list(
        (
            await session.execute(
                select(Guarantee)
                .where(Guarantee.contract_id == contract_id)
                .order_by(Guarantee.expiry_date.nulls_last(), Guarantee.created_at, Guarantee.id)
            )
        )
        .scalars()
        .all()
    )


@router.get("/contracts/{contract_id}/guarantees", response_model=list[GuaranteeOut])
async def list_contract_guarantees(
    contract_id: uuid.UUID, _: ContractReader, session: SessionDep
) -> list[GuaranteeOut]:
    contract = await contract_or_404(session, contract_id)
    today = today_local()
    rows = await _guarantees_of(session, contract.id)
    findings = await guarantee_findings(session, contract, rows, today)
    return [_guarantee_out(g, today, findings) for g in rows]


@router.get("/contracts/{contract_id}/guarantee-checks", response_model=list[FindingOut])
async def guarantee_checks(
    contract_id: uuid.UUID, _: ContractReader, session: SessionDep
) -> list[FindingOut]:
    contract = await contract_or_404(session, contract_id)
    rows = await _guarantees_of(session, contract.id)
    return [
        _finding_out(f) for f in await guarantee_findings(session, contract, rows, today_local())
    ]


@router.post("/contracts/{contract_id}/guarantees", response_model=GuaranteeOut, status_code=201)
async def create_guarantee(
    contract_id: uuid.UUID,
    body: GuaranteeIn,
    request: Request,
    user: ContractWriter,
    session: SessionDep,
) -> GuaranteeOut:
    contract = await contract_or_404(session, contract_id)
    data = body.model_dump(exclude_unset=True)
    _reject_nulls(data, _G_NON_NULL)
    await _require_org(session, data.get("provider_org_id"))
    g = Guarantee(contract_id=contract.id, created_by=user.id, updated_by=user.id, **data)
    session.add(g)
    await session.flush()
    _audit(
        session, user, request, "create", "guarantee", g.id, {"contract_id": contract.id, **data}
    )
    await session.commit()
    await session.refresh(g)
    today = today_local()
    findings = await guarantee_findings(
        session, contract, await _guarantees_of(session, contract.id), today
    )
    return _guarantee_out(g, today, findings)


async def _guarantee_or_404(session: AsyncSession, guarantee_id: uuid.UUID) -> Guarantee:
    g = await session.get(Guarantee, guarantee_id)
    if g is None:
        raise AppError(404, "not_found", "Không tìm thấy bảo lãnh")
    await contract_or_404(session, g.contract_id)  # refuses another project's contract
    return g


@router.patch("/guarantees/{guarantee_id}", response_model=GuaranteeOut)
async def update_guarantee(
    guarantee_id: uuid.UUID,
    body: GuaranteeUpdate,
    request: Request,
    user: ContractWriter,
    session: SessionDep,
) -> GuaranteeOut:
    g = await _guarantee_or_404(session, guarantee_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, _G_NON_NULL)
    await _require_org(session, changes.get("provider_org_id"))
    before = audit.snapshot(g, changes)
    for field, value in changes.items():
        setattr(g, field, value)
    g.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(g, changes))
    if delta:
        _audit(session, user, request, "update", "guarantee", g.id, delta)
    await session.commit()
    await session.refresh(g)
    contract = await contract_or_404(session, g.contract_id)
    today = today_local()
    findings = await guarantee_findings(
        session, contract, await _guarantees_of(session, contract.id), today
    )
    return _guarantee_out(g, today, findings)


@router.delete("/guarantees/{guarantee_id}", status_code=204)
async def delete_guarantee(
    guarantee_id: uuid.UUID, request: Request, user: ContractWriter, session: SessionDep
) -> Response:
    g = await _guarantee_or_404(session, guarantee_id)
    _audit(session, user, request, "delete", "guarantee", g.id, {"contract_id": g.contract_id})
    await session.delete(g)
    await session.commit()
    return Response(status_code=204)


@router.get("/guarantees", response_model=Page[GuaranteeRow])
async def list_guarantees(
    _: ContractReader,
    session: SessionDep,
    pagination: PaginationDep,
    status: str | None = None,
    guarantee_type: str | None = None,
    expiring_within_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
) -> Page[GuaranteeRow]:
    """All guarantees, soonest expiry first (SPEC 6: `/contracts` shows expiring ones on top)."""
    today = today_local()
    stmt = (
        select(Guarantee, Contract, Package)
        .join(Contract, Contract.id == Guarantee.contract_id)
        .join(Package, Package.id == Contract.package_id)
        .where(
            Contract.deleted_at.is_(None),
            Package.deleted_at.is_(None),
            Package.project_id == current_project_id(),
        )
    )
    if guarantee_type:
        stmt = stmt.where(Guarantee.guarantee_type == guarantee_type)
    rows = (await session.execute(stmt)).all()

    by_contract: dict[uuid.UUID, list[Guarantee]] = defaultdict(list)
    contracts: dict[uuid.UUID, Contract] = {}
    for g, c, _p in rows:
        by_contract[c.id].append(g)
        contracts[c.id] = c
    findings: dict[uuid.UUID, list[Finding]] = {
        cid: await guarantee_findings(session, contracts[cid], gs, today)
        for cid, gs in by_contract.items()
    }

    items: list[GuaranteeRow] = []
    for g, c, p in rows:
        eff = effective_status(g, today)
        left = days_left(g.expiry_date, today)
        if status and eff != status:
            continue
        if expiring_within_days is not None and (left is None or left > expiring_within_days):
            continue
        base = _guarantee_out(g, today, findings[c.id])
        items.append(
            GuaranteeRow(
                **base.model_dump(),
                contract_no=c.contract_no,
                package_id=p.id,
                package_number=p.number,
                package_name=p.name,
            )
        )
    items.sort(
        key=lambda r: (
            r.expiry_date is None,
            r.expiry_date or date.max,
            r.package_number,
            r.guarantee_type,
        )
    )
    window = items[pagination.offset : pagination.offset + pagination.page_size]
    return Page[GuaranteeRow](
        items=window, total=len(items), page=pagination.page, page_size=pagination.page_size
    )


# --- payments --------------------------------------------------------------------------------


async def _payment_or_404(session: AsyncSession, payment_id: uuid.UUID) -> Payment:
    p = await session.get(Payment, payment_id)
    if p is None:
        raise AppError(404, "not_found", "Không tìm thấy khoản thanh toán")
    await contract_or_404(session, p.contract_id)  # refuses another project's contract
    return p


@router.get("/contracts/{contract_id}/payments", response_model=list[PaymentOut])
async def list_contract_payments(
    contract_id: uuid.UUID, _: PaymentReader, session: SessionDep
) -> list[Payment]:
    await contract_or_404(session, contract_id)
    return list(
        (
            await session.execute(
                select(Payment)
                .where(Payment.contract_id == contract_id)
                .order_by(Payment.payment_type, Payment.seq, Payment.id)
            )
        )
        .scalars()
        .all()
    )


@router.post("/contracts/{contract_id}/payments", response_model=PaymentOut, status_code=201)
async def create_payment(
    contract_id: uuid.UUID,
    body: PaymentIn,
    request: Request,
    user: PaymentWriter,
    session: SessionDep,
) -> Payment:
    await contract_or_404(session, contract_id)
    data = body.model_dump(exclude_unset=True)
    _reject_nulls(data, _P_NON_NULL)
    if data.get("status", "planned") not in {"planned", "requested"}:
        raise AppError(
            422,
            "validation_error",
            "Khoản mới chỉ có thể ở trạng thái kế hoạch hoặc đã đề nghị",
            ["status"],
        )
    await _require_org(session, data.get("organization_id"))
    if data.get("status") == "requested":
        data.setdefault("requested_date", today_local())
    p = Payment(contract_id=contract_id, created_by=user.id, updated_by=user.id, **data)
    session.add(p)
    await session.flush()
    _audit(session, user, request, "create", "payment", p.id, {"contract_id": contract_id, **data})
    await session.commit()
    await session.refresh(p)
    return p


@router.patch("/payments/{payment_id}", response_model=PaymentOut)
async def update_payment(
    payment_id: uuid.UUID,
    body: PaymentUpdate,
    request: Request,
    user: PaymentWriter,
    session: SessionDep,
) -> Payment:
    p = await _payment_or_404(session, payment_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, _P_NON_NULL)
    if p.status == "paid":
        raise AppError(409, "conflict", "Khoản đã thanh toán, không thể sửa")
    await _require_org(session, changes.get("organization_id"))

    new_status = changes.get("status")
    if new_status is not None and new_status != p.status:
        if new_status == "paid":
            raise AppError(400, "bad_request", "Dùng thao tác mark-paid để ghi nhận thanh toán")
        if new_status not in PAYMENT_TRANSITIONS[p.status]:
            raise AppError(400, "bad_request", f"Không thể chuyển từ {p.status} sang {new_status}")
        if new_status in APPROVAL_TARGETS and not can(
            user.effective_role, "payment", Level.APPROVE
        ):
            raise AppError(403, "forbidden", "Chỉ người có quyền duyệt mới được duyệt hoặc từ chối")
        if new_status == "requested":
            changes.setdefault("requested_date", p.requested_date or today_local())
    elif new_status == p.status:
        changes.pop("status")

    before = audit.snapshot(p, changes)
    for field, value in changes.items():
        setattr(p, field, value)
    p.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(p, changes))
    if delta:
        _audit(session, user, request, "update", "payment", p.id, delta)
    await session.commit()
    await session.refresh(p)
    return p


@router.post("/payments/{payment_id}/mark-paid", response_model=PaymentOut)
async def mark_paid(
    payment_id: uuid.UUID,
    request: Request,
    user: PaymentWriter,
    session: SessionDep,
    body: MarkPaid | None = None,
) -> Payment:
    p = await _payment_or_404(session, payment_id)
    if p.status != "approved":
        raise AppError(409, "conflict", "Chỉ khoản đã được duyệt mới ghi nhận thanh toán")
    body = body or MarkPaid()
    before = audit.snapshot(p, ("status", "paid_date", "treasury_ref"))
    p.status = "paid"
    p.paid_date = body.paid_date or today_local()
    if body.treasury_ref is not None:
        p.treasury_ref = body.treasury_ref
    p.updated_by = user.id
    _audit(
        session,
        user,
        request,
        "update",
        "payment",
        p.id,
        audit.diff(before, audit.snapshot(p, ("status", "paid_date", "treasury_ref"))),
    )
    await session.commit()
    await session.refresh(p)
    return p


@router.get("/payments", response_model=Page[PaymentRow])
async def list_payments(
    _: PaymentReader,
    session: SessionDep,
    pagination: PaginationDep,
    status: str | None = None,
    payment_type: str | None = None,
) -> Page[PaymentRow]:
    stmt = (
        select(Payment, Contract, Package)
        .join(Contract, Contract.id == Payment.contract_id)
        .join(Package, Package.id == Contract.package_id)
        .where(
            Contract.deleted_at.is_(None),
            Package.deleted_at.is_(None),
            Package.project_id == current_project_id(),
        )
    )
    if status:
        stmt = stmt.where(Payment.status == status)
    if payment_type:
        stmt = stmt.where(Payment.payment_type == payment_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(Package.number, Payment.payment_type, Payment.seq)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).all()
    items = [
        PaymentRow(
            **PaymentOut.model_validate(p).model_dump(),
            contract_no=c.contract_no,
            package_id=pkg.id,
            package_number=pkg.number,
            package_name=pkg.name,
        )
        for p, c, pkg in rows
    ]
    return Page[PaymentRow](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


# --- disbursement plan -----------------------------------------------------------------------


def _plan_out(rows: list[DisbursementPlan]) -> DisbursementPlanOut:
    items = [
        DisbursementItem(
            package_id=r.package_id,
            year=r.year,
            month=r.month,
            planned_amount=r.planned_amount,
            actual_amount=r.actual_amount,
        )
        for r in sorted(rows, key=lambda r: (r.year, r.month, str(r.package_id)))
    ]
    return DisbursementPlanOut(
        items=items,
        planned_total=sum((r.planned_amount for r in rows), Decimal(0)),
        actual_total=sum((r.actual_amount or Decimal(0) for r in rows), Decimal(0)),
    )


async def _plan_rows(session: AsyncSession, project_id: uuid.UUID) -> list[DisbursementPlan]:
    return list(
        (
            await session.execute(
                select(DisbursementPlan).where(DisbursementPlan.project_id == project_id)
            )
        )
        .scalars()
        .all()
    )


@router.get("/project/disbursement-plan", response_model=DisbursementPlanOut)
async def read_disbursement_plan(
    _: PaymentReader, session: SessionDep, project: ProjectDep
) -> DisbursementPlanOut:
    return _plan_out(await _plan_rows(session, project.id))


@router.put("/project/disbursement-plan", response_model=DisbursementPlanOut)
async def replace_disbursement_plan(
    body: DisbursementPlanIn,
    request: Request,
    user: PaymentWriter,
    session: SessionDep,
    project: ProjectDep,
) -> DisbursementPlanOut:
    keys = [(i.package_id, i.year, i.month) for i in body.items]
    if len(keys) != len(set(keys)):
        raise AppError(
            422, "validation_error", "Trùng kỳ (gói, năm, tháng) trong kế hoạch giải ngân"
        )
    package_ids = {i.package_id for i in body.items if i.package_id}
    if package_ids:
        found = set(
            (
                await session.execute(
                    select(Package.id).where(
                        Package.id.in_(package_ids), Package.project_id == project.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if missing := package_ids - found:
            raise AppError(
                422, "validation_error", "Gói thầu không thuộc dự án", sorted(map(str, missing))
            )

    before = await _plan_rows(session, project.id)
    await session.execute(delete(DisbursementPlan).where(DisbursementPlan.project_id == project.id))
    rows = [
        DisbursementPlan(
            project_id=project.id,
            package_id=i.package_id,
            year=i.year,
            month=i.month,
            planned_amount=i.planned_amount,
            actual_amount=i.actual_amount,
            created_by=user.id,
            updated_by=user.id,
        )
        for i in body.items
    ]
    session.add_all(rows)
    _audit(
        session,
        user,
        request,
        "update",
        "disbursement_plan",
        project.id,
        {
            "rows": {"before": len(before), "after": len(rows)},
            "planned_total": {
                "before": sum((r.planned_amount for r in before), Decimal(0)),
                "after": sum((r.planned_amount for r in rows), Decimal(0)),
            },
        },
    )
    await session.commit()
    return _plan_out(await _plan_rows(session, project.id))
