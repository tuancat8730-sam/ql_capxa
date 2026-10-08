"""Excel import (SPEC 4.13): contract goods lines with a dry run before anything is written."""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import ContractItem, User
from app.routers.contracts import contract_or_404
from app.schemas.types import Number
from app.services import audit
from app.services.import_items import (
    HEADERS,
    MAX_BYTES,
    ImportFileError,
    ParsedItem,
    parse_workbook,
)
from app.services.xlsx import Col, Row, build_sheet, xlsx_response

router = APIRouter(prefix="/import", tags=["import"])

Writer = Annotated[User, Depends(require("contract", Level.WRITE))]

PREVIEW_ROWS = 20
ONE_DONG = Decimal(1)


class RowErrorOut(BaseModel):
    row: int
    field: str
    message: str


class PreviewItem(BaseModel):
    row: int
    line_no: int
    name: str
    unit: str | None
    quantity: Number | None
    unit_price: Number | None
    amount: Number | None


class ImportOut(BaseModel):
    dry_run: bool
    rows_total: int
    rows_valid: int
    errors: list[RowErrorOut]
    preview: list[PreviewItem]
    total_amount: Number
    contract_value: Number | None
    # None when the contract has no value yet; otherwise whether the lines add up to it
    matches_contract_value: bool | None
    imported: int


def _sequence(items: list[ParsedItem], start: int) -> list[int]:
    """Line numbers: the file's own STT if every row has a distinct one, else count on."""
    given = [i.line_no for i in items]
    if all(n is not None for n in given) and len(set(given)) == len(given) and start == 0:
        return [n for n in given if n is not None]
    return [start + k for k in range(1, len(items) + 1)]


@router.get("/contract-items/template.xlsx")
async def contract_items_template(_: Writer) -> Response:
    """An empty workbook with the expected columns and one example row."""
    columns = [Col(h, "text", 22 if h == "Tên hàng hóa" else 16) for h in HEADERS]
    example = Row(
        ["1", "Máy tính xách tay", "Cái", 10, 15_000_000, 150_000_000, 36, "", "Việt Nam", ""]
    )
    content = build_sheet(
        "Hàng hóa",
        "DANH MỤC HÀNG HÓA HỢP ĐỒNG",
        "Xóa dòng ví dụ rồi nhập từ dòng 5; để trống 'Thành tiền' nếu muốn hệ thống tự tính",
        columns,
        [example],
    )
    return xlsx_response(content, "mau-hang-hoa-hop-dong.xlsx")


@router.post("/contract-items", response_model=ImportOut)
async def import_contract_items(
    request: Request,
    user: Writer,
    session: SessionDep,
    contract_id: Annotated[uuid.UUID, Query()],
    file: Annotated[UploadFile, File()],
    commit: bool = False,
    replace: bool = False,
) -> ImportOut:
    """Dry run by default; `commit=true` writes the lines (all or nothing) only when no row fails.

    `replace=true` removes the contract's existing lines first, otherwise new lines are appended.
    """
    contract = await contract_or_404(session, contract_id)
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise AppError(422, "validation_error", "Chỉ nhận tệp Excel .xlsx", ["file"])
    content = await file.read(MAX_BYTES + 1)
    try:
        parsed = parse_workbook(content)
    except ImportFileError as exc:
        raise AppError(422, "invalid_import_file", str(exc), ["file"]) from exc

    existing_max = 0
    if not replace:
        existing_max = (
            await session.execute(
                select(func.coalesce(func.max(ContractItem.line_no), 0)).where(
                    ContractItem.contract_id == contract_id
                )
            )
        ).scalar_one()
    numbers = _sequence(parsed.items, existing_max)
    total = parsed.total_amount
    value = contract.value
    matches = None if value is None else abs(total - value) <= ONE_DONG
    errors = [RowErrorOut(row=e.row, field=e.field, message=e.message) for e in parsed.errors]

    imported = 0
    if commit:
        if errors:
            raise AppError(
                422,
                "import_has_errors",
                f"Có {len(errors)} lỗi, chưa nhập dòng nào",
                [e.model_dump() for e in errors],
            )
        if not parsed.items:
            raise AppError(422, "invalid_import_file", "Tệp không có dòng hàng hóa", ["file"])
        if replace:
            await session.execute(
                delete(ContractItem).where(ContractItem.contract_id == contract_id)
            )
        for item, line_no in zip(parsed.items, numbers, strict=True):
            session.add(
                ContractItem(
                    contract_id=contract_id,
                    line_no=line_no,
                    name=item.name,
                    unit=item.unit,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    amount=item.amount,
                    warranty_months=item.warranty_months,
                    requires_calibration=item.requires_calibration,
                    origin=item.origin,
                    notes=item.notes,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
        imported = len(parsed.items)
        audit.record(
            session,
            action="create",
            entity_type="contract_items_import",
            entity_id=contract_id,
            user_id=user.id,
            changes={"rows": imported, "replace": replace, "total_amount": total},
            request=request,
        )
        await session.commit()

    return ImportOut(
        dry_run=not commit,
        rows_total=parsed.rows_seen,
        rows_valid=len(parsed.items),
        errors=errors,
        preview=[
            PreviewItem(
                row=i.row,
                line_no=n,
                name=i.name,
                unit=i.unit,
                quantity=i.quantity,
                unit_price=i.unit_price,
                amount=i.amount,
            )
            for i, n in list(zip(parsed.items, numbers, strict=True))[:PREVIEW_ROWS]
        ],
        total_amount=total,
        contract_value=value,
        matches_contract_value=matches,
        imported=imported,
    )
