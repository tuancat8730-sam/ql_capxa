from pathlib import Path

from app.services.tracking_workbook import (
    SEVERITY_WARNING,
    read_tracking_workbook,
    to_vnd,
)

WORKBOOK = (
    Path(__file__).resolve().parents[3] / "docs" / "Tracking_Cac_Goi_Thau_DA_Cap_Xa_Lam_Dong.xlsx"
)


def test_to_vnd_treats_zero_and_blank_as_not_set() -> None:
    # Arrange / Act / Assert
    assert to_vnd(None) is None
    assert to_vnd(0.0) is None
    assert to_vnd("") is None
    assert to_vnd(237382337.0) == 237382337
    assert to_vnd("1.234.567") == 1234567


def test_reads_eight_execution_and_three_preparation_packages() -> None:
    snapshot = read_tracking_workbook(WORKBOOK)

    assert [p.code for p in snapshot.exec_packages] == [f"{n:02d}" for n in range(1, 9)]
    assert [p.code for p in snapshot.preparation_packages] == ["CBDT-01", "CBDT-02", "CBDT-03"]


def test_package_03_is_unsigned_and_package_04_has_its_advance() -> None:
    snapshot = read_tracking_workbook(WORKBOOK)
    by_code = {p.code: p for p in snapshot.packages}

    assert by_code["03"].contract_value is None
    assert by_code["04"].contract_value == 51_505_400_000
    assert by_code["04"].advance == 15_451_620_000


def test_stated_totals_mismatch_is_reported_as_warning_not_error() -> None:
    snapshot = read_tracking_workbook(WORKBOOK)
    mismatches = [f for f in snapshot.findings if f.code == "total_mismatch"]

    assert not snapshot.has_errors
    assert mismatches and all(f.severity == SEVERITY_WARNING for f in mismatches)
    assert any("198,275,859,690" in f.message for f in mismatches)
