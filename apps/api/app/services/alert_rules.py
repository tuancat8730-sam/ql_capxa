"""Alert rules (SPEC 7.1) and package health (SPEC 7.3).

Pure functions over plain facts: the engine in `alert_engine.py` gathers the facts from the
database, calls these and persists the result. Guarantee rules live in `guarantee_rules.py`.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

Severity = Literal["info", "warning", "critical"]

CONTRACT_ENDING_DAYS = 14
CONTRACT_ENDING_CRITICAL_DAYS = 5
PROGRESS_WARN_POINTS = Decimal(10)
PROGRESS_CRIT_POINTS = Decimal(25)
PAYMENT_DUE_DAYS = 5
# An open supply package without a contract has no end date yet; a supervision contract that
# ends within this horizon cannot be confirmed to cover it (SPEC 14.7 expects the alert).
UNSIGNED_SUPPLY_HORIZON_DAYS = 90
DAILY_LOG_HOUR = 17
MONTHLY_REPORT_DAY = 25
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


@dataclass(frozen=True)
class Candidate:
    """An alert the rules want to exist right now."""

    alert_type: str
    severity: Severity
    entity_type: str
    entity_id: str
    title: str
    message: str
    package_id: str | None = None
    due_date: date | None = None
    level: str = ""  # part of the fingerprint when one rule has distinct levels per entity

    @property
    def fingerprint(self) -> str:
        """rule_code + entity_id + level (SPEC 7.1): one condition never makes two alerts."""
        return f"{self.alert_type}:{self.entity_id}:{self.level}"


# --- CONTRACT_ENDING ---------------------------------------------------------------------------


def contract_ending(
    *,
    contract_id: str,
    package_id: str,
    package_label: str,
    end: date | None,
    progress_pct: Decimal,
    today: date,
) -> list[Candidate]:
    if end is None or progress_pct >= 100:
        return []
    days = (end - today).days
    if days > CONTRACT_ENDING_DAYS:
        return []
    critical = days <= CONTRACT_ENDING_CRITICAL_DAYS
    if days < 0:
        message = f"Hợp đồng đã quá hạn {-days} ngày, tiến độ mới {progress_pct:.0f}%"
    else:
        message = f"Còn {days} ngày đến ngày kết thúc hợp đồng, tiến độ mới {progress_pct:.0f}%"
    return [
        Candidate(
            "CONTRACT_ENDING",
            "critical" if critical else "warning",
            "contract",
            contract_id,
            f"{package_label}: hợp đồng sắp kết thúc",
            message,
            package_id=package_id,
            due_date=end,
        )
    ]


# --- STAGE_DELAYED -----------------------------------------------------------------------------


def stage_delayed(
    *,
    stage_id: str,
    package_id: str,
    package_label: str,
    stage_name: str,
    status: str,
    planned_end: date | None,
    progress_pct: Decimal,
    today: date,
) -> list[Candidate]:
    if status == "done" or planned_end is None or planned_end >= today or progress_pct >= 100:
        return []
    late = (today - planned_end).days
    return [
        Candidate(
            "STAGE_DELAYED",
            "warning",
            "stage_plan",
            stage_id,
            f"{package_label}: giai đoạn {stage_name} chậm",
            f"Quá ngày kế hoạch kết thúc {late} ngày, tiến độ giai đoạn {progress_pct:.0f}%",
            package_id=package_id,
            due_date=planned_end,
        )
    ]


# --- PROGRESS_BEHIND ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageSchedule:
    weight: Decimal
    planned_start: date | None
    planned_end: date | None
    status: str


def stage_planned_fraction(s: StageSchedule, today: date) -> Decimal | None:
    """Share of a stage that should be finished by `today`; None without planned dates."""
    if s.status == "done":
        return Decimal(1)
    if s.planned_start is None or s.planned_end is None:
        return None
    if today >= s.planned_end:
        return Decimal(1)
    if today < s.planned_start:
        return Decimal(0)
    total = (s.planned_end - s.planned_start).days + 1
    elapsed = (today - s.planned_start).days + 1
    return Decimal(elapsed) / Decimal(total)


def planned_progress(stages: list[StageSchedule], today: date) -> Decimal | None:
    """Weighted planned progress in % (linear inside each stage); None if nothing is scheduled."""
    total = Decimal(0)
    weighted = Decimal(0)
    scheduled = False
    for s in stages:
        total += s.weight
        frac = stage_planned_fraction(s, today)
        if frac is None:
            continue
        scheduled = True
        weighted += frac * s.weight * 100
    if not scheduled or total == 0:
        return None
    return (weighted / total).quantize(Decimal("0.01"))


def progress_gap(actual: Decimal, planned: Decimal | None) -> Decimal:
    """Points the package is behind plan (0 when on or ahead of plan or no plan)."""
    if planned is None:
        return Decimal(0)
    return max(planned - actual, Decimal(0))


def progress_behind(
    *,
    package_id: str,
    package_label: str,
    actual: Decimal,
    planned: Decimal | None,
) -> list[Candidate]:
    gap = progress_gap(actual, planned)
    if planned is None or gap <= PROGRESS_WARN_POINTS:
        return []
    critical = gap > PROGRESS_CRIT_POINTS
    return [
        Candidate(
            "PROGRESS_BEHIND",
            "critical" if critical else "warning",
            "package",
            package_id,
            f"{package_label}: tiến độ chậm {gap:.0f} điểm %",
            f"Thực tế {actual:.0f}% so với kế hoạch {planned:.0f}%",
            package_id=package_id,
        )
    ]


# --- ISSUE_SLA ---------------------------------------------------------------------------------


def issue_sla(
    *,
    issue_id: str,
    code: str,
    title: str,
    package_id: str | None,
    due_at: datetime | None,
    status: str,
    now: datetime,
) -> list[Candidate]:
    """Overdue issue: warning, and critical once it is more than one day late."""
    if due_at is None or status in {"resolved", "closed"} or now <= due_at:
        return []
    late = now - due_at
    critical = late > timedelta(days=1)
    return [
        Candidate(
            "ISSUE_SLA",
            "critical" if critical else "warning",
            "issue",
            issue_id,
            f"Vướng mắc {code} quá hạn xử lý",
            f"{title} - quá hạn {late.days} ngày" if late.days else f"{title} - quá hạn trong ngày",
            package_id=package_id,
            due_date=due_at.date(),
        )
    ]


# --- DOC_MISSING -------------------------------------------------------------------------------

_STAGE_INDEX = {
    "S1_START": 1,
    "S2_SELECTION": 2,
    "S3_EXECUTION": 3,
    "S4_ACCEPTANCE": 4,
    "S5_PAYMENT_SETTLEMENT": 5,
}


def stage_reached(current_stage: str, item_stage: str) -> bool:
    """True once the package has entered the stage the checklist item belongs to."""
    return _STAGE_INDEX.get(current_stage, 0) >= _STAGE_INDEX.get(item_stage, 99)


def doc_missing(
    *,
    package_id: str,
    package_label: str,
    package_status: str,
    current_stage: str,
    missing: list[tuple[str, str, str]],
) -> list[Candidate]:
    """One alert per package listing required items still missing for stages already entered.

    `missing` holds (item_id, stage_code, title) of required, status=missing checklist items.
    """
    if package_status in {"cancelled", "planning"}:
        return []
    due = [(i, t) for i, stage, t in missing if stage_reached(current_stage, stage)]
    if not due:
        return []
    shown = "; ".join(t for _, t in due[:3])
    more = f" và {len(due) - 3} mục khác" if len(due) > 3 else ""
    return [
        Candidate(
            "DOC_MISSING",
            "warning",
            "package",
            package_id,
            f"{package_label}: thiếu {len(due)} hồ sơ bắt buộc",
            f"Còn thiếu: {shown}{more}",
            package_id=package_id,
        )
    ]


# --- DAILY_LOG_MISSING -------------------------------------------------------------------------


def daily_log_missing(
    *,
    package_id: str,
    package_label: str,
    package_status: str,
    has_log_today: bool,
    now_local: datetime,
    holidays: frozenset[date],
) -> list[Candidate]:
    today = now_local.date()
    if package_status != "executing" or has_log_today:
        return []
    if now_local.hour < DAILY_LOG_HOUR or today.weekday() >= 5 or today in holidays:
        return []
    return [
        Candidate(
            "DAILY_LOG_MISSING",
            "info",
            "package",
            package_id,
            f"{package_label}: chưa có nhật ký hôm nay",
            f"Chưa có nhật ký ngày {today:%d/%m/%Y} sau 17:00",
            package_id=package_id,
            due_date=today,
            level=today.isoformat(),
        )
    ]


# --- REPORT_DUE --------------------------------------------------------------------------------


def _quarter_report_day(today: date) -> date | None:
    """Last day of a quarter, when the quarterly report falls due."""
    if today.month not in (3, 6, 9, 12):
        return None
    nxt = date(today.year + (today.month // 12), today.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def report_due(today: date) -> list[Candidate]:
    """Weekly (Friday), monthly (25th) and quarterly (last day of quarter) reports."""
    out: list[Candidate] = []
    if today.weekday() == 4:
        out.append(
            Candidate(
                "REPORT_DUE",
                "info",
                "report",
                "weekly",
                "Báo cáo tuần đến hạn",
                f"Hôm nay thứ Sáu {today:%d/%m/%Y}: gửi báo cáo tuần",
                due_date=today,
                level=today.isoformat(),
            )
        )
    if today.day == MONTHLY_REPORT_DAY:
        out.append(
            Candidate(
                "REPORT_DUE",
                "info",
                "report",
                "monthly",
                "Báo cáo tháng đến hạn",
                f"Ngày {today:%d/%m/%Y}: gửi báo cáo tháng {today.month}",
                due_date=today,
                level=f"{today.year}-{today.month:02d}",
            )
        )
    if _quarter_report_day(today) == today:
        quarter = (today.month - 1) // 3 + 1
        out.append(
            Candidate(
                "REPORT_DUE",
                "info",
                "report",
                "quarterly",
                "Báo cáo quý đến hạn",
                f"Cuối quý {quarter}/{today.year}: gửi báo cáo quý",
                due_date=today,
                level=f"{today.year}-Q{quarter}",
            )
        )
    return out


# --- CROSS_PKG_DEPENDENCY ----------------------------------------------------------------------


@dataclass(frozen=True)
class ContractEnd:
    package_id: str
    package_label: str
    package_type: str
    consulting_role: str | None
    end: date | None
    status: str  # package status


def cross_package_dependency(
    contracts: list[ContractEnd], acceptance_dates: dict[str, date], today: date
) -> list[Candidate]:
    """TVGS ends before the last supply package; TVQLDA ends before the planned acceptance.

    `acceptance_dates` maps package id -> planned end of its acceptance stage (S4). Open supply
    packages that have no contract yet count as "end unknown": a TVGS contract ending within
    `UNSIGNED_SUPPLY_HORIZON_DAYS` cannot be confirmed to cover them.
    """
    closed = {"cancelled", "settled"}
    open_supply = [c for c in contracts if c.package_type == "goods" and c.status not in closed]
    dated = [c for c in open_supply if c.end is not None]
    unsigned = [c for c in open_supply if c.end is None]
    last = max(dated, key=lambda c: c.end or date.min) if dated else None
    horizon = today + timedelta(days=UNSIGNED_SUPPLY_HORIZON_DAYS)
    out: list[Candidate] = []
    for c in contracts:
        if c.end is None or c.status in closed:
            continue
        if c.consulting_role == "tvgs":
            if last is not None and last.end is not None and c.end < last.end:
                out.append(
                    Candidate(
                        "CROSS_PKG_DEPENDENCY",
                        "warning",
                        "package",
                        c.package_id,
                        f"{c.package_label}: hợp đồng TVGS kết thúc trước gói cung cấp cuối",
                        f"TVGS kết thúc {c.end:%d/%m/%Y}, {last.package_label} kết thúc "
                        f"{last.end:%d/%m/%Y}",
                        package_id=c.package_id,
                        due_date=c.end,
                        level="tvgs",
                    )
                )
            elif unsigned and c.end <= horizon:
                names = ", ".join(u.package_label for u in unsigned)
                out.append(
                    Candidate(
                        "CROSS_PKG_DEPENDENCY",
                        "warning",
                        "package",
                        c.package_id,
                        f"{c.package_label}: hợp đồng TVGS có thể kết thúc trước gói cung cấp",
                        f"TVGS kết thúc {c.end:%d/%m/%Y}; {names} chưa có hợp đồng nên chưa "
                        "xác nhận được thời gian giám sát bao phủ",
                        package_id=c.package_id,
                        due_date=c.end,
                        level="tvgs",
                    )
                )
        if c.consulting_role == "tvqlda" and acceptance_dates:
            last_acceptance = max(acceptance_dates.values())
            if c.end < last_acceptance:
                out.append(
                    Candidate(
                        "CROSS_PKG_DEPENDENCY",
                        "warning",
                        "package",
                        c.package_id,
                        f"{c.package_label}: hợp đồng TVQLDA kết thúc trước nghiệm thu dự kiến",
                        f"TVQLDA kết thúc {c.end:%d/%m/%Y}, nghiệm thu dự kiến "
                        f"{last_acceptance:%d/%m/%Y}",
                        package_id=c.package_id,
                        due_date=c.end,
                        level="tvqlda",
                    )
                )
    return out


# --- PAYMENT_DUE -------------------------------------------------------------------------------


def payment_due(
    *,
    payment_id: str,
    package_id: str,
    package_label: str,
    due_date: date | None,
    status: str,
    today: date,
) -> list[Candidate]:
    """Instalment due within 5 days (or late) that is not yet approved or paid."""
    if due_date is None or status in {"approved", "paid", "rejected"}:
        return []
    days = (due_date - today).days
    if days > PAYMENT_DUE_DAYS:
        return []
    when = f"quá hạn {-days} ngày" if days < 0 else f"còn {days} ngày"
    return [
        Candidate(
            "PAYMENT_DUE",
            "warning",
            "payment",
            payment_id,
            f"{package_label}: đợt thanh toán sắp đến hạn",
            f"Đợt thanh toán {when} (hạn {due_date:%d/%m/%Y}), chưa đủ điều kiện",
            package_id=package_id,
            due_date=due_date,
        )
    ]


# --- package health (SPEC 7.3) -----------------------------------------------------------------


@dataclass(frozen=True)
class Health:
    value: Literal["green", "amber", "red", "grey"]
    reason: str


def package_health(
    *,
    status: str,
    has_contract: bool,
    open_severities: list[str],
    gap: Decimal,
) -> Health:
    """red: critical alert open or >25 points late; amber: warning or >10 points; else green.

    grey for a package that has not started (no contract yet) or is closed.
    """
    if status in {"settled", "cancelled", "accepted"}:
        return Health("grey", "Gói đã đóng")
    if not has_contract:
        return Health("grey", "Chưa có hợp đồng")
    if "critical" in open_severities:
        n = open_severities.count("critical")
        return Health("red", f"{n} cảnh báo nghiêm trọng đang mở")
    if gap > PROGRESS_CRIT_POINTS:
        return Health("red", f"Tiến độ chậm {gap:.0f} điểm %")
    if "warning" in open_severities:
        n = open_severities.count("warning")
        return Health("amber", f"{n} cảnh báo cần chú ý")
    if gap > PROGRESS_WARN_POINTS:
        return Health("amber", f"Tiến độ chậm {gap:.0f} điểm %")
    return Health("green", "Không có cảnh báo")
