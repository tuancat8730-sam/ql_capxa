"""The folders of the SGD-HCM archive ("Tài Liệu Lưu trữ").

`documents` (SPEC 3.18) has no folder column: a document sits in a folder when it carries the tag
`folder:<code>`. Codes stay short because a tag is at most 50 characters.
"""

import re
from dataclasses import dataclass

TAG_PREFIX = "folder:"


@dataclass(frozen=True)
class Folder:
    code: str
    group: str
    label: str
    doc_type: str


FOLDERS: tuple[Folder, ...] = (
    Folder("chung", "Chung", "Tài liệu chung", "project_doc"),
    Folder(
        "nha-thau-1",
        "Nhà thầu",
        "1. Quản lý dự án (Kế hoạch, Báo cáo, Nhật ký thi công)",
        "schedule_plan",
    ),
    Folder(
        "nha-thau-2",
        "Nhà thầu",
        "2. Thủ tục hành chính (Công văn, Tờ trình, Đề xuất, Phê duyệt)",
        "admin_procedure",
    ),
    Folder(
        "nha-thau-3",
        "Nhà thầu",
        "3. Nghiệp vụ (Quy trình nghiệp vụ, biểu mẫu, TL khảo sát)",
        "business_doc",
    ),
    Folder(
        "nha-thau-4",
        "Nhà thầu",
        "4. Phần mềm (Yêu cầu, Đặc tả, Thiết kế, Kiểm thử, HDSD)",
        "software_doc",
    ),
    Folder(
        "nha-thau-5",
        "Nhà thầu",
        "5. Nghiệm thu, bàn giao (Biên bản, hồ sơ, tài liệu)",
        "handover_doc",
    ),
    Folder("giam-sat", "Giám sát", "Giám sát", "project_doc"),
)
FOLDER_BY_CODE = {f.code: f for f in FOLDERS}

_CONTRACTOR = "nhà thầu"
_SUPERVISOR = "giám sát"
_NUMBERED = re.compile(r"^\s*([1-5])\s*\.")


def folder_tag(code: str) -> str:
    return f"{TAG_PREFIX}{code}"


def folder_code_for(parts: tuple[str, ...]) -> str:
    """Folder of a file from the names of the directories above it (relative to the archive)."""
    if not parts:
        return "chung"
    top = parts[0].strip().casefold()
    if top == _SUPERVISOR:
        return "giam-sat"
    if top == _CONTRACTOR and len(parts) > 1:
        numbered = _NUMBERED.match(parts[1])
        if numbered:
            return f"nha-thau-{numbered.group(1)}"
    return "chung"
