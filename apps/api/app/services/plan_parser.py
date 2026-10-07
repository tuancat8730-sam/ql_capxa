"""Turn a `RawDoc` into a structured delivery plan, plus the consistency findings of SPEC-style
rules. Pure functions: no database, no HTTP.

Reads three things: the header facts (contract and implementation periods, places, signer), the
equipment table ("Stt | Tên thiết bị | ĐVT | Khối lượng | Nhà thầu đảm nhiệm | Ghi chú") and the
steps table ("STT | Nội dung công việc | Thời gian | Thành phần tham gia", with stage rows
"BƯỚC n: ..."). Whatever it cannot read is left empty and reported, never guessed.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from app.services.plan_reader import PlanFileError, RawDoc, RawTable
from app.services.search import fold

_DATE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})")
_STAGE = re.compile(r"^b[uư][oơ]c\s*(\d+)\s*[:.\-]?\s*(.*)$", re.IGNORECASE)
_ASSIGN = re.compile(r"^(?P<org>.+?)\s*:\s*(?P<qty>[\d.,]+)\s*(?P<unit>[^\d:]*)$")
_ESTIMATE_WORDS = ("du kien", "du tru")


@dataclass
class ParsedItem:
    line_no: int
    name: str
    details: str | None = None
    unit: str | None = None
    quantity: int | None = None
    assignments: list[dict[str, object]] = field(default_factory=list)
    note: str | None = None


@dataclass
class ParsedStep:
    step_no: int
    content: str
    group_no: int | None = None
    group_title: str | None = None
    time_text: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated: bool = False
    time_note: str | None = None
    participants: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        return content_hash(self.content)


@dataclass
class ParsedPlan:
    addressee: str | None = None
    legal_basis: str | None = None
    contract_text: str | None = None
    contract_start: date | None = None
    contract_end: date | None = None
    implement_text: str | None = None
    implement_start: date | None = None
    implement_end: date | None = None
    locations: list[dict[str, str]] = field(default_factory=list)
    signer: str | None = None
    declared_total: int | None = None
    items: list[ParsedItem] = field(default_factory=list)
    steps: list[ParsedStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str  # warning | info
    message: str


def content_hash(content: str) -> str:
    """Same wording (ignoring case, accents and spacing) gives the same fingerprint."""
    normal = " ".join(fold(content).split())
    return hashlib.sha1(normal.encode()).hexdigest()  # noqa: S324 - a fingerprint, not security


# --- small readers -------------------------------------------------------------------------------


def parse_dates(text: str) -> tuple[list[date], list[str]]:
    """Every dd/mm/yyyy in the text, plus the ones that are not real dates (31/02/2026)."""
    found: list[date] = []
    bad: list[str] = []
    for d, m, y in _DATE.findall(text):
        try:
            found.append(date(int(y), int(m), int(d)))
        except ValueError:
            bad.append(f"{d}/{m}/{y}")
    return found, bad


def _period(text: str) -> tuple[date | None, date | None]:
    dates, _ = parse_dates(text)
    if not dates:
        return None, None
    return dates[0], dates[-1]


def _int(text: str) -> int | None:
    digits = re.sub(r"[^\d]", "", text.split("\n")[0])
    return int(digits) if digits else None


def _after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip() if ":" in line else line.strip()


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside brackets: "A, B (C, D), E" -> A, B (C, D), E."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in text.replace("\n", " "):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


# --- header --------------------------------------------------------------------------------------


def _parse_header(lines: list[str], plan: ParsedPlan) -> None:
    in_places = False
    sign_at: int | None = None
    for i, line in enumerate(lines):
        key = fold(line)
        if key.startswith("kinh gui"):
            plan.addressee = _after_colon(line)
        elif key.startswith("can cu") and plan.legal_basis is None:
            plan.legal_basis = line
        elif "thoi gian thuc hien hop dong" in key:
            plan.contract_text = _after_colon(line)
            plan.contract_start, plan.contract_end = _period(plan.contract_text)
        elif "thoi gian trien khai" in key:
            plan.implement_text = _after_colon(line)
            plan.implement_start, plan.implement_end = _period(plan.implement_text)
        elif "dia diem trien khai" in key:
            in_places = True
        elif in_places and re.match(r"^\s*(\d+[.)]|noi dung trien khai)", key):
            in_places = False
        elif in_places and line.lstrip().startswith(("-", "–", "•")):
            text = line.lstrip("-–• ").strip()
            label, _, rest = text.partition(":")
            if rest and len(label) <= 140:
                plan.locations.append({"label": label.strip(), "text": rest.strip()})
            else:
                plan.locations.append({"label": "", "text": text})
        elif "thanh vien dung dau lien danh" in key:
            sign_at = i
    if sign_at is not None:
        tail = [ln for ln in lines[sign_at + 1 : sign_at + 6] if ln.strip()]
        if tail:
            plan.signer = " – ".join(tail[:3])


# --- equipment table -----------------------------------------------------------------------------


def _header_index(table: RawTable) -> dict[str, int] | None:
    for row in table.rows[:3]:
        keys = [" ".join(fold(c).split()) for c in row]
        if any(k in {"stt", "tt"} for k in keys):
            return {k: i for i, k in enumerate(keys) if k}
    return None


def _column(header: dict[str, int], *needles: str) -> int | None:
    for key, idx in header.items():
        if any(key.startswith(n) or n in key for n in needles):
            return idx
    return None


def _assignments(cell: str, quantity: int | None) -> list[dict[str, object]]:
    lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
    out: list[dict[str, object]] = []
    for line in lines:
        m = _ASSIGN.match(line)
        if m:
            out.append({"org": m.group("org").strip(), "quantity": _int(m.group("qty"))})
        else:
            out.append({"org": line, "quantity": None})
    if len(out) == 1 and out[0]["quantity"] is None and quantity is not None:
        out[0]["quantity"] = quantity  # one contractor does the whole line
    return out


def _parse_items(table: RawTable, plan: ParsedPlan) -> None:
    header = _header_index(table)
    assert header is not None
    c_name = _column(header, "ten thiet bi", "ten hang", "noi dung")
    c_unit = _column(header, "dvt", "don vi")
    c_qty = _column(header, "khoi luong", "so luong")
    c_who = _column(header, "nha thau", "dam nhiem")
    c_note = _column(header, "ghi chu")
    if c_name is None:
        plan.warnings.append("Bảng thiết bị không có cột 'Tên thiết bị'")
        return

    def cell(row: list[str], idx: int | None) -> str:
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    started = False
    for row in table.rows:
        first = cell(row, 0)
        if not started:
            started = any(k in {"stt", "tt"} for k in (fold(c).strip() for c in row))
            continue
        if "tong cong" in fold(" ".join(row)):
            total = _int(cell(row, c_qty))
            plan.declared_total = total
            continue
        if not first.strip().isdigit() or not cell(row, c_name):
            continue
        lines = cell(row, c_name).split("\n")
        quantity = _int(cell(row, c_qty))
        plan.items.append(
            ParsedItem(
                line_no=int(first),
                name=lines[0].strip(),
                details="\n".join(lines[1:]).strip() or None,
                unit=cell(row, c_unit) or None,
                quantity=quantity,
                assignments=_assignments(cell(row, c_who), quantity) if cell(row, c_who) else [],
                note=cell(row, c_note) or None,
            )
        )


# --- steps table ---------------------------------------------------------------------------------


def _parse_steps(table: RawTable, plan: ParsedPlan) -> None:
    header = _header_index(table)
    assert header is not None
    c_content = _column(header, "noi dung")
    c_time = _column(header, "thoi gian")
    c_who = _column(header, "thanh phan", "tham gia")
    if c_content is None:
        plan.warnings.append("Bảng các bước không có cột 'Nội dung công việc'")
        return

    def cell(row: list[str], idx: int | None) -> str:
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    group_no: int | None = None
    group_title: str | None = None
    started = False
    for row in table.rows:
        if not started:
            started = any(k in {"stt", "tt"} for k in (fold(c).strip() for c in row))
            continue
        if len(row) == 1:
            m = _STAGE.match(fold_keep_case(row[0]))
            if m:
                group_no, group_title = int(m.group(1)), m.group(2).strip().rstrip(":") or None
            continue
        first = cell(row, 0)
        content = cell(row, c_content)
        if not first.isdigit() or not content:
            continue
        time_text = " ".join(cell(row, c_time).split()) or None
        start = end = None
        estimated = False
        note = None
        if time_text:
            dates, bad = parse_dates(time_text)
            if bad:
                plan.warnings.append(f"Bước {first}: ngày không hợp lệ ({', '.join(bad)})")
            if dates:
                start, end = dates[0], dates[-1]
            estimated = any(w in fold(time_text) for w in _ESTIMATE_WORDS)
            brackets = re.findall(r"\(([^)]*)\)", time_text)
            note = "; ".join(b.strip() for b in brackets if b.strip()) or None
        plan.steps.append(
            ParsedStep(
                step_no=int(first),
                content=content,
                group_no=group_no,
                group_title=group_title,
                time_text=time_text,
                start_date=start,
                end_date=end,
                estimated=estimated,
                time_note=note,
                participants=_split_top_level(cell(row, c_who)),
            )
        )


def fold_keep_case(text: str) -> str:
    """The stage heading with accents removed from the keyword only: "BƯỚC 1: KIỂM TRA ..."."""
    head = text.strip()
    m = re.match(r"^(b\S+c)\s*(\d+)\s*[:.\-]?\s*(.*)$", head, re.IGNORECASE | re.DOTALL)
    if m and fold(m.group(1)) == "buoc":
        return f"buoc {m.group(2)}: {m.group(3)}"
    return head


# --- entry point ---------------------------------------------------------------------------------


def parse_plan(raw: RawDoc) -> ParsedPlan:
    plan = ParsedPlan()
    _parse_header(raw.lines, plan)

    items_table = steps_table = None
    for table in raw.tables:
        header = _header_index(table)
        if header is None:
            continue
        if items_table is None and _column(header, "ten thiet bi", "ten hang") is not None:
            items_table = table
        elif steps_table is None and _column(header, "noi dung cong viec", "noi dung") is not None:
            steps_table = table
    if items_table is None and steps_table is None:
        raise PlanFileError("Không nhận ra bảng thiết bị hay bảng các bước triển khai trong tệp")
    if items_table is not None:
        _parse_items(items_table, plan)
    else:
        plan.warnings.append("Không thấy bảng thiết bị")
    if steps_table is not None:
        _parse_steps(steps_table, plan)
    else:
        plan.warnings.append("Không thấy bảng các bước triển khai")
    if not plan.items and not plan.steps:
        raise PlanFileError("Các bảng trong tệp không có dòng thiết bị hay bước nào đọc được")
    return plan


# --- consistency findings ------------------------------------------------------------------------


def plan_findings(plan: ParsedPlan, *, contract_end: date | None = None) -> list[Finding]:
    """Things in the plan that do not add up. They are shown, never block saving."""
    out: list[Finding] = []
    end_of_contract = plan.contract_end or contract_end

    total = sum(i.quantity or 0 for i in plan.items)
    if plan.declared_total is not None and plan.items and total != plan.declared_total:
        out.append(
            Finding(
                "QUANTITY_TOTAL",
                "warning",
                f"Tổng số lượng các hạng mục là {total} nhưng dòng tổng cộng ghi "
                f"{plan.declared_total}",
            )
        )
    for item in plan.items:
        shares = [a["quantity"] for a in item.assignments if isinstance(a["quantity"], int)]
        if (
            item.quantity is not None
            and len(shares) == len(item.assignments) > 1
            and sum(shares) != item.quantity
        ):
            out.append(
                Finding(
                    "ASSIGNMENT_TOTAL",
                    "warning",
                    f"Hạng mục {item.line_no}: số lượng chia cho các nhà thầu ({sum(shares)}) "
                    f"khác khối lượng {item.quantity}",
                )
            )

    dated = [s for s in plan.steps if s.end_date is not None]
    if end_of_contract is not None and dated:
        last = max(dated, key=lambda s: s.end_date or date.min)
        if last.end_date and last.end_date > end_of_contract:
            late = [s for s in dated if s.end_date and s.end_date > end_of_contract]
            out.append(
                Finding(
                    "AFTER_CONTRACT_END",
                    "warning",
                    f"{len(late)} bước kết thúc sau ngày kết thúc hợp đồng "
                    f"{end_of_contract:%d/%m/%Y} (muộn nhất {last.end_date:%d/%m/%Y})",
                )
            )
    if plan.implement_end is not None and dated:
        last = max(dated, key=lambda s: s.end_date or date.min)
        if last.end_date and last.end_date > plan.implement_end:
            out.append(
                Finding(
                    "AFTER_IMPLEMENT_END",
                    "info",
                    f"Các bước kéo dài tới {last.end_date:%d/%m/%Y}, sau thời gian triển khai "
                    f"nêu trong kế hoạch ({plan.implement_end:%d/%m/%Y})",
                )
            )
    undated = [s.step_no for s in plan.steps if s.start_date is None and s.end_date is None]
    if undated:
        out.append(
            Finding(
                "NO_TIME",
                "info",
                "Chưa có thời gian ở bước " + ", ".join(str(n) for n in undated),
            )
        )
    for w in plan.warnings:
        out.append(Finding("READ_WARNING", "warning", w))
    return out
