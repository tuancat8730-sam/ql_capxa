"""Read the weekly tracking workbook (`00_TONG_HOP`) into an immutable snapshot with checks.

Read-only: nothing is written to the database here. Rows are found by their label in column A,
not by fixed row numbers, because the file is copied again every week and rows can move.
Money cells may hold floats or text; they are normalised to whole VND.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

SUMMARY_SHEET = "00_TONG_HOP"
EXEC_LABEL = re.compile(r"^Gói số (\d{2})$")
CBDT_LABEL = re.compile(r"^CBĐT - Gói (\d{2})$")
TOTAL_EXEC_LABEL = "TỔNG CỘNG (08 GÓI)"
TOTAL_CBDT_LABEL = "TỔNG CBĐT (03 GÓI)"
TOTAL_PROJECT_LABEL = "TỔNG TOÀN DỰ ÁN"
EXPECTED_EXEC = 8
EXPECTED_CBDT = 3

# Column letters in `00_TONG_HOP` (header row 15 for execution, row 27 for preparation).
COL_CODE, COL_NAME, COL_SCOPE, COL_PRICE, COL_SELECTION = "A", "B", "C", "D", "E"
COL_DURATION, COL_CONTRACTOR, COL_CONTRACT_REF, COL_CONTRACT_VALUE = "F", "G", "H", "I"
COL_CONTRACT_TERM, COL_ADVANCE, COL_PAYMENT, COL_PROGRESS, COL_STATUS = (
    "J",
    "K",
    "L",
    "M",
    "N",
)
COL_DETAIL = "O"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class PackageRow:
    code: str  # "01".."08" (QĐ 239) or "CBDT-01".."CBDT-03"
    is_preparation: bool
    name: str
    scope: str
    price: int
    selection: str
    duration: str
    contractor: str
    contract_ref: str
    contract_value: int | None
    contract_term: str
    advance: int | None
    payment_note: str
    progress_note: str
    status: str
    detail_sheet: str


@dataclass(frozen=True)
class TrackingSnapshot:
    source: str
    read_at: datetime
    packages: tuple[PackageRow, ...]
    stated_totals: dict[str, int | None]
    findings: tuple[Finding, ...]

    @property
    def exec_packages(self) -> tuple[PackageRow, ...]:
        return tuple(p for p in self.packages if not p.is_preparation)

    @property
    def preparation_packages(self) -> tuple[PackageRow, ...]:
        return tuple(p for p in self.packages if p.is_preparation)

    @property
    def has_errors(self) -> bool:
        return any(f.severity == SEVERITY_ERROR for f in self.findings)


def to_vnd(value: Any) -> int | None:
    """Normalise a workbook money cell. Empty and zero both mean "not set" (None)."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"expected money, got bool: {value!r}")
    if isinstance(value, int | float):
        amount = round(value)
    else:
        digits = re.sub(r"[^\d-]", "", str(value))
        if not digits:
            return None
        amount = int(digits)
    return amount or None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _cell(sheet: Any, row: int, column: str) -> Any:
    return sheet[f"{column}{row}"].value


def _row_code(label: str) -> tuple[str, bool] | None:
    """Return (code, is_preparation) for a package label, or None for any other row."""
    if match := EXEC_LABEL.match(label):
        return match.group(1), False
    if match := CBDT_LABEL.match(label):
        return f"CBDT-{match.group(1)}", True
    return None


def _package_from_row(sheet: Any, row: int, code: str, is_preparation: bool) -> PackageRow:
    def text(column: str) -> str:
        return _text(_cell(sheet, row, column))

    return PackageRow(
        code=code,
        is_preparation=is_preparation,
        name=text(COL_NAME),
        scope=text(COL_SCOPE),
        price=to_vnd(_cell(sheet, row, COL_PRICE)) or 0,
        selection=text(COL_SELECTION),
        duration=text(COL_DURATION),
        contractor=text(COL_CONTRACTOR),
        contract_ref=text(COL_CONTRACT_REF),
        contract_value=to_vnd(_cell(sheet, row, COL_CONTRACT_VALUE)),
        contract_term=text(COL_CONTRACT_TERM),
        advance=to_vnd(_cell(sheet, row, COL_ADVANCE)),
        payment_note=text(COL_PAYMENT),
        progress_note=text(COL_PROGRESS),
        status=text(COL_STATUS),
        detail_sheet=text(COL_DETAIL),
    )


def _find_rows(sheet: Any) -> tuple[list[tuple[int, str, bool]], dict[str, int]]:
    """Locate package rows and total rows by their column-A label."""
    package_rows: list[tuple[int, str, bool]] = []
    total_rows: dict[str, int] = {}
    for row in range(1, sheet.max_row + 1):
        label = _text(_cell(sheet, row, COL_CODE))
        if parsed := _row_code(label):
            package_rows.append((row, parsed[0], parsed[1]))
        elif label in (TOTAL_EXEC_LABEL, TOTAL_CBDT_LABEL, TOTAL_PROJECT_LABEL):
            total_rows[label] = row
    return package_rows, total_rows


def _stated_totals(sheet: Any, total_rows: dict[str, int]) -> dict[str, int | None]:
    """Totals as typed in the workbook: price and signed value per total row."""
    stated: dict[str, int | None] = {}
    for label, row in total_rows.items():
        stated[f"{label}:price"] = to_vnd(_cell(sheet, row, COL_PRICE))
        stated[f"{label}:signed"] = to_vnd(_cell(sheet, row, COL_CONTRACT_VALUE))
    return stated


def _check_counts(packages: tuple[PackageRow, ...]) -> list[Finding]:
    exec_count = sum(1 for p in packages if not p.is_preparation)
    cbdt_count = len(packages) - exec_count
    findings: list[Finding] = []
    if exec_count != EXPECTED_EXEC:
        findings.append(
            Finding(
                SEVERITY_ERROR,
                "exec_count",
                f"Có {exec_count} gói thực hiện, cần {EXPECTED_EXEC}",
            )
        )
    if cbdt_count != EXPECTED_CBDT:
        findings.append(
            Finding(
                SEVERITY_ERROR,
                "cbdt_count",
                f"Có {cbdt_count} gói chuẩn bị đầu tư, cần {EXPECTED_CBDT}",
            )
        )
    return findings


def _check_package(package: PackageRow) -> list[Finding]:
    label = f"Gói {package.code}"
    findings: list[Finding] = []
    if package.price <= 0:
        findings.append(Finding(SEVERITY_ERROR, "price_missing", f"{label}: thiếu giá gói"))
    if package.contract_value is not None and package.contract_value > package.price > 0:
        findings.append(
            Finding(SEVERITY_WARNING, "value_above_price", f"{label}: giá HĐ lớn hơn giá gói")
        )
    if package.contract_value and not package.contractor:
        findings.append(
            Finding(
                SEVERITY_ERROR, "contractor_missing", f"{label}: có giá HĐ nhưng thiếu nhà thầu"
            )
        )
    if package.advance and package.contract_value and package.advance > package.contract_value:
        findings.append(
            Finding(SEVERITY_ERROR, "advance_above_value", f"{label}: tạm ứng lớn hơn giá HĐ")
        )
    return findings


def _vnd_text(amount: int | None) -> str:
    return "trống (không có giá trị đã tính)" if amount is None else f"{amount:,}"


def _check_totals(packages: tuple[PackageRow, ...], stated: dict[str, int | None]) -> list[Finding]:
    """Compare each stated total with the sum of its rows; a mismatch is a warning, not an error."""
    expected = {
        f"{TOTAL_EXEC_LABEL}:price": sum(p.price for p in packages if not p.is_preparation),
        f"{TOTAL_CBDT_LABEL}:price": sum(p.price for p in packages if p.is_preparation),
        f"{TOTAL_EXEC_LABEL}:signed": sum(
            p.contract_value or 0 for p in packages if not p.is_preparation
        ),
        f"{TOTAL_CBDT_LABEL}:signed": sum(
            p.contract_value or 0 for p in packages if p.is_preparation
        ),
    }
    findings: list[Finding] = []
    for key, computed in expected.items():
        if key not in stated:
            continue
        if stated[key] != computed:
            findings.append(
                Finding(
                    SEVERITY_WARNING,
                    "total_mismatch",
                    f"{key}: file ghi {_vnd_text(stated[key])}, cộng từ các dòng ra {computed:,}",
                )
            )
    return findings


def read_tracking_workbook(path: Path) -> TrackingSnapshot:
    """Read `00_TONG_HOP` and return the packages with every check result attached."""
    workbook = load_workbook(path, data_only=True, read_only=False)
    sheet = workbook[SUMMARY_SHEET]
    package_rows, total_rows = _find_rows(sheet)
    packages = tuple(
        _package_from_row(sheet, row, code, is_preparation)
        for row, code, is_preparation in package_rows
    )
    stated = _stated_totals(sheet, total_rows)
    findings = [
        *_check_counts(packages),
        *(f for p in packages for f in _check_package(p)),
        *_check_totals(packages, stated),
    ]
    return TrackingSnapshot(
        source=path.name,
        read_at=datetime.now().astimezone(),
        packages=packages,
        stated_totals=stated,
        findings=tuple(findings),
    )
