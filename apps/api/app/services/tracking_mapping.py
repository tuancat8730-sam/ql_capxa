"""Map workbook wording to the app's enum values. Pure functions; unknown wording maps to None.

Each function returns None when the text matches no rule. The sync reports those rows instead of
guessing, so a new phrase in the workbook shows up as a finding rather than a wrong status.
"""

import re

CBDT_NUMBER_OFFSET = 100  # CBDT-01..03 are stored as packages 101..103
RISK_CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("hợp đồng", "contract"),
    ("pháp lý", "legal"),
    ("kiểm định", "quality"),
    ("tiến độ", "schedule"),
    ("chi phí", "cost"),
    ("bảo lãnh", "cost"),
    ("cung ứng", "supply"),
)
# Workbook priority text -> (probability, impact). Compound text uses the first rule that matches.
PRIORITY_SCORES: tuple[tuple[str, tuple[int, int]], ...] = (
    ("Khẩn cấp", (5, 5)),
    ("Rất cao", (4, 5)),
    ("Cao", (4, 4)),
    ("Trung bình", (3, 3)),
    ("Thấp", (2, 2)),
)
_CODE = re.compile(r"^(\d{2})$|^CBDT-(\d{2})$")


def package_number(code: str) -> int | None:
    """ "01".."08" -> 1..8; "CBDT-01".."CBDT-03" -> 101..103."""
    match = _CODE.match(code)
    if not match:
        return None
    if match.group(1):
        return int(match.group(1))
    return CBDT_NUMBER_OFFSET + int(match.group(2))


def selection_form(text: str) -> str | None:
    if "rút gọn" in text:
        return "direct_appointment_short"
    if "Đấu thầu rộng rãi" in text:
        return "open_tender"
    return None


def selection_method(text: str) -> str | None:
    if "rút gọn" in text:
        return "short_procedure"
    if "2 túi" in text:
        return "one_stage_two_envelope"
    if "1 túi" in text:
        return "one_stage_one_envelope"
    return None


def package_health(status: str) -> str | None:
    """Traffic light from the workbook status text (the text itself is kept as health_reason)."""
    if any(word in status for word in ("Chậm", "Vướng")):
        return "red"
    if any(word in status for word in ("Cảnh báo", "Bám sát")):
        return "amber"
    if any(word in status for word in ("Hoàn thành", "Đúng tiến độ", "Đã ký")):
        return "green"
    return None


def task_status(status: str) -> str | None:
    if status.startswith("Hoàn thành"):
        return "done"
    if any(word in status for word in ("Cảnh báo", "trễ", "Vướng", "vướng")):
        return "blocked"
    if status.startswith("Đang"):
        return "doing"
    if status.startswith(("Chưa", "Sắp")):
        return "todo"
    return None


def issue_status(status: str) -> str | None:
    """Workbook "Tình trạng xử lý" -> risk status (open / mitigating / closed)."""
    if status.startswith(("Đã", "Hoàn thành")):
        return "closed"
    if status.startswith("Đang"):
        return "mitigating"
    if status.startswith(("Chưa", "Cần", "Đề xuất")):
        return "open"
    return None


def priority_score(priority: str) -> tuple[int, int] | None:
    for label, score in PRIORITY_SCORES:
        if label in priority:
            return score
    return None


def risk_category(text: str) -> str:
    """First keyword rule that matches the issue title; "other" when none does."""
    lowered = text.lower()
    for keyword, category in RISK_CATEGORY_RULES:
        if keyword in lowered:
            return category
    return "other"


def organization_name(text: str) -> str:
    """Drop the bracketed director: "Công ty X (GĐ: Y)" -> "Công ty X"."""
    return text.split(" (", 1)[0].strip()


def contract_number(reference: str) -> str | None:
    """Number before " ngày": "53/2026/HĐTV/... ngày 20/7/2026" -> "53/2026/HĐTV/..."."""
    head = reference.split(" ngày", 1)[0].strip()
    return head or None


def duration_days(text: str) -> int | None:
    """ "60 Ngày (Trọn gói)" -> 60."""
    match = re.match(r"\s*(\d+)\s*[Nn]gày", text)
    return int(match.group(1)) if match else None
