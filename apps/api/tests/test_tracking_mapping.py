import pytest

from app.services.tracking_mapping import (
    contract_number,
    duration_days,
    issue_status,
    organization_name,
    package_health,
    package_number,
    priority_score,
    risk_category,
    selection_form,
    selection_method,
    task_status,
)


@pytest.mark.parametrize(
    ("code", "number"),
    [("01", 1), ("08", 8), ("CBDT-01", 101), ("CBDT-03", 103), ("9", None), ("CBDT-1", None)],
)
def test_package_number_puts_preparation_packages_beside_execution_ones(
    code: str, number: int | None
) -> None:
    assert package_number(code) == number


def test_selection_wording_maps_to_form_and_method() -> None:
    text = "Đấu thầu rộng rãi qua mạng; 1 giai đoạn 1 túi hồ sơ (45 ngày)"
    assert selection_form(text) == "open_tender"
    assert selection_method(text) == "one_stage_one_envelope"
    assert selection_form("Chỉ định thầu rút gọn (15 ngày)") == "direct_appointment_short"
    assert selection_method("Chỉ định thầu rút gọn (15 ngày)") == "short_procedure"


def test_unknown_selection_wording_is_none_not_guessed() -> None:
    assert selection_form("Hình thức khác") is None
    assert selection_method("Hình thức khác") is None


@pytest.mark.parametrize(
    ("status", "health"),
    [
        ("Chậm tiến độ LCNT (Vướng mắc)", "red"),
        ("Đang thực hiện (Cảnh báo hạn HĐ)", "amber"),
        ("Đang thực hiện (Đúng tiến độ)", "green"),
        ("Hoàn thành (Đã thanh toán)", "green"),
        ("Tình trạng lạ", None),
    ],
)
def test_package_health_reads_the_status_text(status: str, health: str | None) -> None:
    assert package_health(status) == health


@pytest.mark.parametrize(
    ("status", "task"),
    [
        ("Hoàn thành", "done"),
        ("Đang thực hiện", "doing"),
        ("Đang xử lý vướng mắc", "blocked"),
        ("Cảnh báo trễ hạn HĐ", "blocked"),
        ("Sắp thực hiện (Bắt đầu 30/10)", "todo"),
        ("Chưa thực hiện", "todo"),
        ("Lạ", None),
    ],
)
def test_milestone_status_mapping(status: str, task: str | None) -> None:
    assert task_status(status) == task


@pytest.mark.parametrize(
    ("status", "risk"),
    [
        ("Đã hoàn thành", "closed"),
        ("Đang trình CĐT", "mitigating"),
        ("Chưa xử lý", "open"),
        ("?", None),
    ],
)
def test_issue_status_mapping(status: str, risk: str | None) -> None:
    assert issue_status(status) == risk


def test_priority_uses_first_matching_level_and_rejects_unknown() -> None:
    assert priority_score("Khẩn cấp / Rất cao") == (5, 5)
    assert priority_score("Rất cao") == (4, 5)
    assert priority_score("Cao") == (4, 4)
    assert priority_score("") is None


def test_risk_category_defaults_to_other() -> None:
    assert risk_category("Vướng mắc pháp lý về xuất xứ") == "legal"
    assert risk_category("Chậm tiến độ bàn giao") == "schedule"
    assert risk_category("Vấn đề khác") == "other"


def test_contractor_and_contract_text_are_trimmed_to_the_identifier() -> None:
    assert (
        organization_name("Công ty TNHH Nguyên Luân (GĐ: Nguyễn Thanh Luân)")
        == "Công ty TNHH Nguyên Luân"
    )
    assert contract_number("71/2026/SKHCNLĐ-NL ngày 14/9/2026 (QĐ 355)") == "71/2026/SKHCNLĐ-NL"
    assert duration_days("60 Ngày (Trọn gói)") == 60
    assert duration_days("không rõ") is None
