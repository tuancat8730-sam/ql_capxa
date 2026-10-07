"""List exports (SPEC 4.13): QL-07 contract tracking, risks, issues, alerts, document checklist."""

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import SessionDep, require
from app.core.rbac import Level
from app.models import (
    Alert,
    ChecklistItem,
    Contract,
    Document,
    Guarantee,
    Issue,
    Package,
    Payment,
    Risk,
    User,
)
from app.routers.project import get_single_project
from app.services import audit
from app.services.documents import accessible_package_ids, can_view
from app.services.finance import today_local
from app.services.risk_rules import risk_level
from app.services.xlsx import Col, Row, as_date, build_sheet, xlsx_response

router = APIRouter(prefix="/export", tags=["export"])

PaymentReader = Annotated[User, Depends(require("payment", Level.READ))]
RiskReader = Annotated[User, Depends(require("risk", Level.READ))]
PackageReader = Annotated[User, Depends(require("package", Level.READ))]
DocumentReader = Annotated[User, Depends(require("document", Level.READ))]

RISK_CATEGORY = {
    "schedule": "Tiến độ",
    "cost": "Chi phí",
    "quality": "Chất lượng",
    "legal": "Pháp lý",
    "contract": "Hợp đồng",
    "supply": "Cung ứng",
    "safety": "An toàn",
    "other": "Khác",
}
RISK_STATUS = {
    "open": "Đang mở",
    "mitigating": "Đang giảm thiểu",
    "occurred": "Đã xảy ra",
    "closed": "Đã đóng",
}
RISK_LEVEL = {"low": "Thấp", "medium": "Trung bình", "high": "Cao"}
ISSUE_TYPE = {
    "operational": "Tác nghiệp",
    "contract": "Hợp đồng",
    "schedule": "Tiến độ",
    "investor_request": "Yêu cầu của chủ đầu tư",
    "other": "Khác",
}
ISSUE_STATUS = {
    "open": "Mới",
    "in_progress": "Đang xử lý",
    "escalated": "Đã chuyển cấp",
    "resolved": "Đã giải quyết",
    "closed": "Đã đóng",
}
SEVERITY = {"critical": "Nghiêm trọng", "warning": "Cần chú ý", "info": "Thông tin"}
ALERT_STATUS = {
    "open": "Đang mở",
    "acknowledged": "Đã xác nhận",
    "resolved": "Đã tự đóng",
    "suppressed": "Đang hoãn",
}
ALERT_TYPE = {
    "GUARANTEE_EXPIRING": "Bảo lãnh sắp hết hạn",
    "ADVANCE_GUARANTEE_SHORT": "Bảo lãnh tạm ứng không đủ thời hạn",
    "GUARANTEE_MISSING": "Thiếu bảo lãnh",
    "CONTRACT_ENDING": "Hợp đồng sắp kết thúc",
    "STAGE_DELAYED": "Giai đoạn chậm",
    "PROGRESS_BEHIND": "Tiến độ chậm",
    "ISSUE_SLA": "Vướng mắc quá hạn",
    "DOC_MISSING": "Thiếu hồ sơ",
    "DAILY_LOG_MISSING": "Chưa có nhật ký",
    "REPORT_DUE": "Báo cáo đến hạn",
    "CROSS_PKG_DEPENDENCY": "Phụ thuộc giữa các gói",
    "PAYMENT_DUE": "Thanh toán đến hạn",
    "PLAN_STEP_OVERDUE": "Bước kế hoạch quá hạn",
}
STAGE = {
    "S1_START": "Khởi động",
    "S2_SELECTION": "Lựa chọn nhà thầu",
    "S3_EXECUTION": "Thực hiện hợp đồng",
    "S4_ACCEPTANCE": "Nghiệm thu bàn giao",
    "S5_PAYMENT_SETTLEMENT": "Thanh toán, quyết toán",
}
CHECKLIST_STATUS = {"missing": "Chưa có", "received": "Đã có", "not_applicable": "Không áp dụng"}

_MIN_DATE = date.min
_MAX_DATE = date.max


def _label(number: int | None) -> str:
    return f"Gói {number:02d}" if number is not None else "Chung"


async def _finish(
    session: AsyncSession, request: Request, user: User, entity: str, rows: int, content: bytes
) -> Response:
    audit.record(
        session,
        action="export",
        entity_type=entity,
        entity_id=None,
        user_id=user.id,
        changes={"rows": rows},
        request=request,
    )
    await session.commit()
    return xlsx_response(content, f"{entity}-{today_local():%Y%m%d}.xlsx")


async def _numbers(session: AsyncSession) -> dict[object, int]:
    rows = await session.execute(select(Package.id, Package.number))
    return {pid: n for pid, n in rows.all()}


async def _user_names(session: AsyncSession) -> dict[object, str]:
    return {u.id: u.full_name for u in (await session.execute(select(User))).scalars()}


async def _subtitle(session: AsyncSession) -> str:
    project = await get_single_project(session)
    return f"{project.name} — xuất ngày {today_local():%d/%m/%Y}"


# --- QL-07 -------------------------------------------------------------------------------------

QL07_COLUMNS = (
    Col("Gói", "text", 8),
    Col("Nhà thầu", "text", 28),
    Col("Số hợp đồng", "text", 14),
    Col("Ngày ký", "date", 13),
    Col("Giá trị hợp đồng (VND)", "money", 20),
    Col("Hạn hợp đồng", "date", 13),
    Col("Bảo đảm thực hiện (VND)", "money", 20),
    Col("Hạn bảo đảm thực hiện", "date", 14),
    Col("Tạm ứng (VND)", "money", 18),
    Col("Bảo lãnh tạm ứng (VND)", "money", 20),
    Col("Hạn bảo lãnh tạm ứng", "date", 14),
    Col("Thanh toán lũy kế (VND)", "money", 20),
    Col("Tạm ứng đã thu hồi (VND)", "money", 20),
    Col("Tạm ứng còn dư (VND)", "money", 20),
)
_QL07_SUMMED = (4, 6, 8, 9, 11, 12, 13)


def _pick(guarantees: list[Guarantee], kind: str) -> Guarantee | None:
    """The guarantee of a kind that is still in force (latest expiry first)."""
    live = [
        g
        for g in guarantees
        if g.guarantee_type == kind and g.status not in {"released", "missing"}
    ]
    return max(live, key=lambda g: g.expiry_date or _MIN_DATE, default=None)


@router.get("/ql07.xlsx")
async def export_ql07(request: Request, user: PaymentReader, session: SessionDep) -> Response:
    """One row per contract with guarantees, advance and payments, plus a totals row."""
    contracts = (
        await session.execute(
            select(Contract, Package)
            .join(Package, Package.id == Contract.package_id)
            .where(Contract.deleted_at.is_(None), Package.deleted_at.is_(None))
            .order_by(Package.number, Contract.contract_no)
        )
    ).all()
    guarantees: dict[object, list[Guarantee]] = defaultdict(list)
    for g in (await session.execute(select(Guarantee))).scalars():
        guarantees[g.contract_id].append(g)
    paid: dict[object, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for p in (await session.execute(select(Payment).where(Payment.status == "paid"))).scalars():
        paid[p.contract_id][p.payment_type] += p.amount

    rows: list[Row] = []
    sums = dict.fromkeys(_QL07_SUMMED, Decimal(0))
    for contract, package in contracts:
        perf = _pick(guarantees[contract.id], "performance")
        adv = _pick(guarantees[contract.id], "advance")
        by_type = paid[contract.id]
        recovered = by_type["recovery"]
        advance = contract.advance_amount
        values = [
            _label(package.number),
            package.winning_org_text,
            contract.contract_no,
            contract.signed_date,
            contract.value,
            contract.extended_end_date or contract.planned_end_date,
            perf.amount if perf else None,
            perf.expiry_date if perf else None,
            advance,
            adv.amount if adv else None,
            adv.expiry_date if adv else None,
            by_type["advance"] + by_type["payment"],
            recovered,
            max(advance - recovered, Decimal(0)) if advance is not None else None,
        ]
        rows.append(Row(values))
        for i in _QL07_SUMMED:
            if values[i] is not None:
                sums[i] += Decimal(str(values[i]))
    content = build_sheet(
        "QL-07",
        "BẢNG THEO DÕI HỢP ĐỒNG (QL-07)",
        await _subtitle(session),
        QL07_COLUMNS,
        rows,
        dict(sums),
    )
    return await _finish(session, request, user, "QL-07", len(rows), content)


# --- risks and issues --------------------------------------------------------------------------


@router.get("/risks.xlsx")
async def export_risks(request: Request, user: RiskReader, session: SessionDep) -> Response:
    numbers = await _numbers(session)
    names = await _user_names(session)
    risks = (
        (await session.execute(select(Risk).order_by(Risk.score.desc(), Risk.code))).scalars().all()
    )
    columns = (
        Col("Mã", "text", 9),
        Col("Gói", "text", 9),
        Col("Rủi ro", "text", 44),
        Col("Nhóm", "text", 13),
        Col("Xác suất (1-5)", "int", 11),
        Col("Tác động (1-5)", "int", 11),
        Col("Điểm", "int", 8),
        Col("Mức", "text", 12),
        Col("Trạng thái", "text", 16),
        Col("Chủ trì", "text", 20),
        Col("Hạn", "date", 13),
        Col("Biện pháp", "text", 44),
    )
    rows = []
    for r in risks:
        level = risk_level(r.score)
        rows.append(
            Row(
                [
                    r.code,
                    _label(numbers.get(r.package_id)),
                    r.title,
                    RISK_CATEGORY.get(r.category, r.category),
                    r.probability,
                    r.impact,
                    r.score,
                    RISK_LEVEL[level],
                    RISK_STATUS.get(r.status, r.status),
                    names.get(r.owner_id) if r.owner_id else None,
                    r.due_date,
                    r.mitigation,
                ],
                hot=frozenset({6, 7}) if level == "high" and r.status != "closed" else frozenset(),
            )
        )
    content = build_sheet("Rủi ro", "SỔ RỦI RO", await _subtitle(session), columns, rows)
    return await _finish(session, request, user, "rui-ro", len(rows), content)


@router.get("/issues.xlsx")
async def export_issues(request: Request, user: RiskReader, session: SessionDep) -> Response:
    numbers = await _numbers(session)
    names = await _user_names(session)
    tz = ZoneInfo(get_settings().app_timezone)
    now = datetime.now(UTC)
    issues = (await session.execute(select(Issue).order_by(Issue.code))).scalars().all()
    columns = (
        Col("Mã", "text", 9),
        Col("Gói", "text", 9),
        Col("Loại", "text", 20),
        Col("Cấp", "int", 6),
        Col("Vướng mắc", "text", 44),
        Col("Trạng thái", "text", 16),
        Col("Ngày ghi nhận", "date", 14),
        Col("Hạn xử lý", "date", 14),
        Col("Người xử lý", "text", 20),
        Col("Kết quả xử lý", "text", 40),
    )
    rows = []
    for i in issues:
        overdue = i.due_at is not None and i.status not in {"resolved", "closed"} and i.due_at < now
        rows.append(
            Row(
                [
                    i.code,
                    _label(numbers.get(i.package_id)),
                    ISSUE_TYPE.get(i.issue_type, i.issue_type),
                    i.level,
                    i.title,
                    ISSUE_STATUS.get(i.status, i.status),
                    as_date(i.reported_at.astimezone(tz)),
                    as_date(i.due_at.astimezone(tz)) if i.due_at else None,
                    names.get(i.assigned_to) if i.assigned_to else None,
                    i.resolution,
                ],
                hot=frozenset({7}) if overdue else frozenset(),
            )
        )
    sheet_title = "DANH SÁCH VƯỚNG MẮC"
    content = build_sheet("Vướng mắc", sheet_title, await _subtitle(session), columns, rows)
    return await _finish(session, request, user, "vuong-mac", len(rows), content)


# --- alerts and checklist ----------------------------------------------------------------------


@router.get("/alerts.xlsx")
async def export_alerts(request: Request, user: PackageReader, session: SessionDep) -> Response:
    numbers = await _numbers(session)
    tz = ZoneInfo(get_settings().app_timezone)
    order = {"critical": 0, "warning": 1, "info": 2}
    open_alerts = (
        (await session.execute(select(Alert).where(Alert.status != "resolved"))).scalars().all()
    )
    alerts = sorted(open_alerts, key=lambda a: (order[a.severity], a.due_date or _MAX_DATE))
    columns = (
        Col("Mức", "text", 14),
        Col("Loại cảnh báo", "text", 30),
        Col("Gói", "text", 9),
        Col("Nội dung", "text", 44),
        Col("Chi tiết", "text", 52),
        Col("Hạn", "date", 13),
        Col("Trạng thái", "text", 14),
        Col("Phát hiện lúc", "datetime", 18),
    )
    rows = [
        Row(
            [
                SEVERITY[a.severity],
                ALERT_TYPE.get(a.alert_type, a.alert_type),
                _label(numbers.get(a.package_id)),
                a.title,
                a.message,
                a.due_date,
                ALERT_STATUS.get(a.status, a.status),
                a.first_seen_at.astimezone(tz),
            ],
            hot=frozenset({0}) if a.severity == "critical" else frozenset(),
        )
        for a in alerts
    ]
    content = build_sheet("Cảnh báo", "DANH SÁCH CẢNH BÁO", await _subtitle(session), columns, rows)
    return await _finish(session, request, user, "canh-bao", len(rows), content)


@router.get("/checklist.xlsx")
async def export_checklist(request: Request, user: DocumentReader, session: SessionDep) -> Response:
    """Checklist items per package; the file behind a line is never named, only its date."""
    packages = {p.id: p for p in (await session.execute(select(Package))).scalars()}
    items = (await session.execute(select(ChecklistItem))).scalars().all()
    docs = {
        d.id: d
        for d in (
            await session.execute(select(Document).where(Document.deleted_at.is_(None)))
        ).scalars()
    }
    today = today_local()
    access_ids = await accessible_package_ids(session, user)
    columns = (
        Col("Gói", "text", 9),
        Col("Giai đoạn", "text", 22),
        Col("Hạng mục hồ sơ", "text", 46),
        Col("Bắt buộc", "text", 10),
        Col("Tình trạng", "text", 14),
        Col("Hạn", "date", 13),
        Col("Ngày văn bản", "date", 14),
        Col("Ghi chú", "text", 36),
    )
    rows = []
    for it in sorted(items, key=lambda i: (packages[i.package_id].number, i.sort_order)):
        doc = docs.get(it.document_id) if it.document_id else None
        if doc is not None and not can_view(user, doc, access_ids):
            doc = None  # a hidden file never shows through the checklist
        overdue = (
            it.status == "missing"
            and it.required
            and it.due_date is not None
            and it.due_date < today
        )
        rows.append(
            Row(
                [
                    _label(packages[it.package_id].number),
                    STAGE.get(it.stage_code, it.stage_code),
                    it.title,
                    "Có" if it.required else "Không",
                    CHECKLIST_STATUS.get(it.status, it.status),
                    it.due_date,
                    doc.doc_date if doc else None,
                    it.note,
                ],
                hot=frozenset({4, 5}) if overdue else frozenset(),
            )
        )
    content = build_sheet("Hồ sơ", "DANH MỤC HỒ SƠ", await _subtitle(session), columns, rows)
    return await _finish(session, request, user, "danh-muc-ho-so", len(rows), content)
