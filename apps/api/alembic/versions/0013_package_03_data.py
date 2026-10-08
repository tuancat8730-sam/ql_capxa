"""Gói 03 (commune project): contract HĐ 41/2026, payment, decisions and risk from SPEC v1.2

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-08 16:00:00.000000

Source: docs/SPEC_QLDA_WebApp_v01.md sections 14.2, 14.3, 14.5 and 14.6. The seed carries the same
data for a fresh database; this migration brings an existing one in line.
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PACKAGE_NOTES = (
    "Giá trị đã bao gồm VAT 10%. Chưa rõ nghiệm thu, thanh lý, thanh toán. "
    "Chứng thư thẩm định giá 194.717.303.146 đ (20/6/2026) hiệu lực đến khoảng "
    "20/9/2026 [OCR]. QĐ 154 ghi nhầm tên dự án, cần đính chính."
)
_PAYMENT_TERMS = (
    "Thanh toán một lần 430.000.000 đ sau nghiệm thu, thanh lý và khi dự án "
    "được phê duyệt; không tạm ứng. Hóa đơn số 87 (2C26TBT) ngày 30/6/2026."
)
_QUALITY_NOTE = (
    "Văn bản ghi thời gian thực hiện ba cách: từ ngày hiệu lực, từ ngày ký, "
    "30 ngày làm việc từ khi đủ hồ sơ; tính theo ngày ký."
)
_OLD_RISK = "Gói 03 chậm ký hợp đồng – nút thắt cung cấp thiết bị"
_NEW_RISK = "Gói 03 chưa rõ nghiệm thu, thanh lý, thanh toán; chứng thư thẩm định giá hết hiệu lực"
_RISK_TEXT = (
    "Chứng thư thẩm định giá (194.717.303.146 đ, 20/6/2026) hết hiệu lực khoảng 20/9/2026 "
    "trong khi các gói thiết bị còn đang thực hiện; QĐ 154 ghi nhầm tên dự án cần đính chính."
)
_RISK_MITIGATION = (
    "Xác nhận nghiệm thu, thanh lý và thanh toán HĐ 41; đề nghị đính chính QĐ 154; "
    "kiểm tra chứng thư có còn được dùng làm căn cứ không."
)
_PROJECT = "(SELECT id FROM projects WHERE code = '8200685' AND deleted_at IS NULL)"


def upgrade() -> None:
    bind = op.get_bind()
    package_id = bind.execute(
        sa.text(
            f"SELECT id FROM packages WHERE project_id = {_PROJECT} "  # noqa: S608
            "AND number = 3 AND deleted_at IS NULL"
        )
    ).scalar()
    if package_id is None:
        return
    bind.execute(
        sa.text(
            "UPDATE packages SET scope_summary = :scope, kh_lcnt_decision = :kh, "
            "approval_decision = :ap, notes = :notes WHERE id = :p"
        ),
        {
            "scope": "Tư vấn thẩm định giá (nhiệm vụ chuẩn bị đầu tư).",
            "kh": "KHLCNT PL2600169648; QĐ 151/QĐ-SKHCN ngày 13/6/2026",
            "ap": "QĐ 154/QĐ-SKHCN ngày 15/6/2026 (phê duyệt KQLCNT)",
            "notes": _PACKAGE_NOTES,
            "p": package_id,
        },
    )
    contract_id = bind.execute(
        sa.text("SELECT id FROM contracts WHERE package_id = :p AND deleted_at IS NULL"),
        {"p": package_id},
    ).scalar()
    if contract_id is None:
        return
    bind.execute(
        sa.text(
            "UPDATE contracts SET contract_no = :no, signed_date = :signed, effective_date = NULL, "
            "duration_days = 30, planned_end_date = :end, end_date_override = false, "
            "contract_type = 'lump_sum', payment_terms_text = :terms, "
            "data_quality_note = :note WHERE id = :id"
        ),
        {
            "no": "41/2026/SKH&CNLĐ-BTA",
            "signed": date(2026, 6, 15),
            "end": date(2026, 7, 14),
            "terms": _PAYMENT_TERMS,
            "note": _QUALITY_NOTE,
            "id": contract_id,
        },
    )
    has_payment = bind.execute(
        sa.text("SELECT 1 FROM payments WHERE contract_id = :c AND payment_type = 'payment'"),
        {"c": contract_id},
    ).first()
    if has_payment is None:
        bind.execute(
            sa.text(
                "INSERT INTO payments (id, contract_id, payment_type, seq, amount, status, "
                "invoice_no, notes) VALUES (gen_random_uuid(), :c, 'payment', 1, 430000000, "
                "'planned', :inv, :notes)"
            ),
            {
                "c": contract_id,
                "inv": "87 (2C26TBT) ngày 30/6/2026",
                "notes": "Một đợt, sau nghiệm thu, thanh lý và khi dự án được phê duyệt; "
                "chưa rõ đã thanh toán.",
            },
        )
    bind.execute(
        sa.text(
            "UPDATE risks SET title = :new, description = :d, category = 'contract', "
            "probability = 4, impact = 5, score = 20, mitigation = :m, source = 'analysis' "
            "WHERE title = :old"
        ),
        {"new": _NEW_RISK, "d": _RISK_TEXT, "m": _RISK_MITIGATION, "old": _OLD_RISK},
    )


def downgrade() -> None:
    """The earlier Gói 03 values were wrong; they are not restored."""
