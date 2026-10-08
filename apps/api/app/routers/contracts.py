import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.core.scope import not_found_unless_in_project
from app.models import (
    Contract,
    ContractAmendment,
    ContractItem,
    ContractParty,
    Organization,
    Package,
    User,
)
from app.routers.packages import package_or_404
from app.schemas.contract import (
    AmendmentIn,
    AmendmentOut,
    AmendmentUpdate,
    ContractCreate,
    ContractOut,
    ContractUpdate,
    ItemIn,
    ItemOut,
    ItemUpdate,
    PartyIn,
    PartyOut,
    PartyUpdate,
)
from app.services import audit
from app.services.contracts import NON_NULLABLE, PARTY_ORDER, apply_planned_end, contract_out

router = APIRouter(tags=["contracts"])

Reader = Annotated[User, Depends(require("contract", Level.READ))]
Writer = Annotated[User, Depends(require("contract", Level.WRITE))]

_CONTRACT_FIELDS = tuple(ContractUpdate.model_fields) + ("planned_end_date",)


async def contract_or_404(session: AsyncSession, contract_id: uuid.UUID) -> Contract:
    contract = await session.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise AppError(404, "not_found", "Không tìm thấy hợp đồng")
    package = await session.get(Package, contract.package_id)
    not_found_unless_in_project(package.project_id if package else None, "Không tìm thấy hợp đồng")
    return contract


def _reject_null_required(changes: dict[str, Any], required: frozenset[str] = NON_NULLABLE) -> None:
    nulls = sorted(k for k, v in changes.items() if v is None and k in required)
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)


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


# --- contracts ---------------------------------------------------------------------------------


@router.get("/packages/{package_id}/contracts", response_model=list[ContractOut])
async def list_contracts(
    package_id: uuid.UUID, _: Reader, session: SessionDep
) -> list[ContractOut]:
    await package_or_404(session, package_id)
    rows = (
        (
            await session.execute(
                select(Contract)
                .where(Contract.package_id == package_id, Contract.deleted_at.is_(None))
                .order_by(Contract.signed_date.nulls_last(), Contract.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [await contract_out(session, c) for c in rows]


@router.post("/packages/{package_id}/contracts", response_model=ContractOut, status_code=201)
async def create_contract(
    package_id: uuid.UUID,
    body: ContractCreate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> ContractOut:
    await package_or_404(session, package_id)
    data = body.model_dump(exclude_unset=True)
    _reject_null_required(data)
    contract = Contract(package_id=package_id, created_by=user.id, updated_by=user.id, **data)
    apply_planned_end(contract, set(data))
    session.add(contract)
    await session.flush()
    _audit(
        session,
        user,
        request,
        "create",
        "contract",
        contract.id,
        {"package_id": package_id, **audit.snapshot(contract, _CONTRACT_FIELDS)},
    )
    await session.commit()
    await session.refresh(contract)
    return await contract_out(session, contract)


@router.get("/contracts/{contract_id}", response_model=ContractOut)
async def read_contract(contract_id: uuid.UUID, _: Reader, session: SessionDep) -> ContractOut:
    return await contract_out(session, await contract_or_404(session, contract_id))


@router.patch("/contracts/{contract_id}", response_model=ContractOut)
async def update_contract(
    contract_id: uuid.UUID,
    body: ContractUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> ContractOut:
    contract = await contract_or_404(session, contract_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_null_required(changes)
    before = audit.snapshot(contract, _CONTRACT_FIELDS)
    for field, value in changes.items():
        setattr(contract, field, value)
    apply_planned_end(contract, set(changes))
    contract.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(contract, _CONTRACT_FIELDS))
    if delta:
        _audit(session, user, request, "update", "contract", contract.id, delta)
    await session.commit()
    await session.refresh(contract)
    return await contract_out(session, contract)


# --- parties (consortium members) ----------------------------------------------------------------


async def _party_out(session: AsyncSession, party: ContractParty) -> PartyOut:
    org = await session.get(Organization, party.organization_id)
    return PartyOut.model_validate(party).model_copy(
        update={"organization_name": org.name if org else None}
    )


async def _require_org(session: AsyncSession, org_id: uuid.UUID | None) -> None:
    if org_id is not None and await session.get(Organization, org_id) is None:
        raise AppError(422, "validation_error", "Tổ chức không tồn tại", ["organization_id"])


@router.get("/contracts/{contract_id}/parties", response_model=list[PartyOut])
async def list_parties(contract_id: uuid.UUID, _: Reader, session: SessionDep) -> list[PartyOut]:
    await contract_or_404(session, contract_id)
    rows = (
        (
            await session.execute(
                select(ContractParty)
                .where(ContractParty.contract_id == contract_id)
                .order_by(PARTY_ORDER, ContractParty.id)
            )
        )
        .scalars()
        .all()
    )
    return [await _party_out(session, p) for p in rows]


@router.post("/contracts/{contract_id}/parties", response_model=PartyOut, status_code=201)
async def create_party(
    contract_id: uuid.UUID, body: PartyIn, request: Request, user: Writer, session: SessionDep
) -> PartyOut:
    await contract_or_404(session, contract_id)
    await _require_org(session, body.organization_id)
    party = ContractParty(
        contract_id=contract_id, created_by=user.id, updated_by=user.id, **body.model_dump()
    )
    session.add(party)
    await session.flush()
    _audit(session, user, request, "create", "contract_party", party.id, body.model_dump())
    await session.commit()
    await session.refresh(party)
    return await _party_out(session, party)


async def _child_or_404[T](session: AsyncSession, model: type[T], child_id: uuid.UUID) -> T:
    child = await session.get(model, child_id)
    if child is None:
        raise AppError(404, "not_found", "Không tìm thấy bản ghi")
    await contract_or_404(session, child.contract_id)  # type: ignore[attr-defined]
    return child


@router.patch("/contract-parties/{party_id}", response_model=PartyOut)
async def update_party(
    party_id: uuid.UUID, body: PartyUpdate, request: Request, user: Writer, session: SessionDep
) -> PartyOut:
    party = await _child_or_404(session, ContractParty, party_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_null_required(changes, frozenset({"role"}))
    before = audit.snapshot(party, changes)
    for field, value in changes.items():
        setattr(party, field, value)
    party.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(party, changes))
    if delta:
        _audit(session, user, request, "update", "contract_party", party.id, delta)
    await session.commit()
    await session.refresh(party)
    return await _party_out(session, party)


@router.delete("/contract-parties/{party_id}", status_code=204)
async def delete_party(
    party_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    party = await _child_or_404(session, ContractParty, party_id)
    _audit(
        session,
        user,
        request,
        "delete",
        "contract_party",
        party.id,
        {"contract_id": party.contract_id},
    )
    await session.delete(party)
    await session.commit()
    return Response(status_code=204)


# --- items -----------------------------------------------------------------------------------


@router.get("/contracts/{contract_id}/items", response_model=list[ItemOut])
async def list_items(contract_id: uuid.UUID, _: Reader, session: SessionDep) -> list[ContractItem]:
    await contract_or_404(session, contract_id)
    return list(
        (
            await session.execute(
                select(ContractItem)
                .where(ContractItem.contract_id == contract_id)
                .order_by(ContractItem.line_no, ContractItem.id)
            )
        )
        .scalars()
        .all()
    )


@router.post("/contracts/{contract_id}/items", response_model=ItemOut, status_code=201)
async def create_item(
    contract_id: uuid.UUID, body: ItemIn, request: Request, user: Writer, session: SessionDep
) -> ContractItem:
    await contract_or_404(session, contract_id)
    data = body.model_dump(exclude_unset=True)
    _reject_null_required(data, frozenset({"line_no", "name", "requires_calibration"}))
    await _require_org(session, data.get("member_org_id"))
    item = ContractItem(contract_id=contract_id, created_by=user.id, updated_by=user.id, **data)
    session.add(item)
    await session.flush()
    _audit(session, user, request, "create", "contract_item", item.id, data)
    await session.commit()
    await session.refresh(item)
    return item


@router.patch("/contract-items/{item_id}", response_model=ItemOut)
async def update_item(
    item_id: uuid.UUID, body: ItemUpdate, request: Request, user: Writer, session: SessionDep
) -> ContractItem:
    item = await _child_or_404(session, ContractItem, item_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_null_required(changes, frozenset({"line_no", "name", "requires_calibration"}))
    await _require_org(session, changes.get("member_org_id"))
    before = audit.snapshot(item, changes)
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(item, changes))
    if delta:
        _audit(session, user, request, "update", "contract_item", item.id, delta)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/contract-items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    item = await _child_or_404(session, ContractItem, item_id)
    _audit(
        session,
        user,
        request,
        "delete",
        "contract_item",
        item.id,
        {"contract_id": item.contract_id},
    )
    await session.delete(item)
    await session.commit()
    return Response(status_code=204)


# --- amendments ------------------------------------------------------------------------------


@router.get("/contracts/{contract_id}/amendments", response_model=list[AmendmentOut])
async def list_amendments(
    contract_id: uuid.UUID, _: Reader, session: SessionDep
) -> list[ContractAmendment]:
    await contract_or_404(session, contract_id)
    return list(
        (
            await session.execute(
                select(ContractAmendment)
                .where(ContractAmendment.contract_id == contract_id)
                .order_by(ContractAmendment.signed_date.nulls_last(), ContractAmendment.created_at)
            )
        )
        .scalars()
        .all()
    )


@router.post("/contracts/{contract_id}/amendments", response_model=AmendmentOut, status_code=201)
async def create_amendment(
    contract_id: uuid.UUID, body: AmendmentIn, request: Request, user: Writer, session: SessionDep
) -> ContractAmendment:
    await contract_or_404(session, contract_id)
    data = body.model_dump(exclude_unset=True)
    amendment = ContractAmendment(
        contract_id=contract_id, created_by=user.id, updated_by=user.id, **data
    )
    session.add(amendment)
    await session.flush()
    _audit(session, user, request, "create", "contract_amendment", amendment.id, data)
    await session.commit()
    await session.refresh(amendment)
    return amendment


@router.patch("/contract-amendments/{amendment_id}", response_model=AmendmentOut)
async def update_amendment(
    amendment_id: uuid.UUID,
    body: AmendmentUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> ContractAmendment:
    amendment = await _child_or_404(session, ContractAmendment, amendment_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_null_required(changes, frozenset({"amendment_no", "type"}))
    before = audit.snapshot(amendment, changes)
    for field, value in changes.items():
        setattr(amendment, field, value)
    amendment.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(amendment, changes))
    if delta:
        _audit(session, user, request, "update", "contract_amendment", amendment.id, delta)
    await session.commit()
    await session.refresh(amendment)
    return amendment


@router.delete("/contract-amendments/{amendment_id}", status_code=204)
async def delete_amendment(
    amendment_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    amendment = await _child_or_404(session, ContractAmendment, amendment_id)
    _audit(
        session,
        user,
        request,
        "delete",
        "contract_amendment",
        amendment.id,
        {"contract_id": amendment.contract_id},
    )
    await session.delete(amendment)
    await session.commit()
    return Response(status_code=204)
