"""correct contractor, value and duration of packages 01, 02, 03, 07, 08 (commune project)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-08 15:00:00.000000

Source: "Sửa thông tin trên web — danh sách nhà thầu, giá trị và thời gian thực hiện các gói thầu".
The seed carries the same data for a fresh database; this migration brings an existing one in line.
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOTE = "Theo danh sách nhà thầu, giá trị và thời gian thực hiện các gói thầu (bản sửa)."

# number, organization, org_type, value, start, end, days, contract_no, note
_ROWS = (
    (1, "Công ty Cổ phần Tư vấn Quang Trung", "consultant", 556_000_000,
     date(2026, 6, 15), date(2026, 7, 30), 45, "53", _NOTE),
    (2, "Công ty TNHH Hưng Dũng Lâm Đồng", "consultant", 70_000_000,
     date(2026, 6, 15), date(2026, 7, 15), 30, "54", _NOTE),
    (3, "Công ty TNHH Thẩm định giá và Đo đạc Địa chính BTA Việt Nam", "consultant", 430_000_000,
     date(2026, 6, 15), date(2026, 7, 15), 30, "Chưa rõ", _NOTE + " Giá trị đã bao gồm VAT 10%."),
    (7, "Sài Gòn Mới", "consultant", 509_000_000,
     date(2026, 9, 15), date(2026, 12, 14), 90, "73", _NOTE),
    (8, "Công ty TNHH Kiểm toán Tư vấn Rồng Việt", "auditor", 710_000_000,
     date(2026, 9, 15), date(2026, 12, 14), 90, "74", _NOTE + " Giá trị: bảy trăm mười triệu đồng chẵn."),
)  # fmt: skip

_PROJECT = "(SELECT id FROM projects WHERE code = '8200685' AND deleted_at IS NULL)"


def upgrade() -> None:
    bind = op.get_bind()
    for number, org, org_type, value, start, end, days, contract_no, note in _ROWS:
        org_id = bind.execute(
            sa.text("SELECT id FROM organizations WHERE name = :n AND deleted_at IS NULL"),
            {"n": org},
        ).scalar()
        if org_id is None:
            org_id = bind.execute(
                sa.text(
                    "INSERT INTO organizations (id, name, short_name, org_type) "
                    "VALUES (gen_random_uuid(), :n, :n, :t) RETURNING id"
                ),
                {"n": org, "t": org_type},
            ).scalar()

        package_id = bind.execute(
            sa.text(
                f"SELECT id FROM packages WHERE project_id = {_PROJECT} "  # noqa: S608
                "AND number = :num AND deleted_at IS NULL"
            ),
            {"num": number},
        ).scalar()
        if package_id is None:  # the commune project is not in this database
            continue

        bind.execute(
            sa.text(
                "UPDATE packages SET package_type = 'consulting', package_price = :v, "
                "winning_price = :v, winning_org_text = :o, approved_duration_days = :d, "
                "status = 'contract_signed', current_stage = 'S3_EXECUTION', "
                "etbmt_no = NULL, health_reason = NULL, notes = NULL WHERE id = :p"
            ),
            {"v": value, "o": org, "d": days, "p": package_id},
        )

        contract_id = bind.execute(
            sa.text("SELECT id FROM contracts WHERE package_id = :p AND deleted_at IS NULL"),
            {"p": package_id},
        ).scalar()
        if contract_id is None:
            contract_id = bind.execute(
                sa.text(
                    "INSERT INTO contracts (id, package_id, contract_no, end_date_override, "
                    "price_adjustment, status) "
                    "VALUES (gen_random_uuid(), :p, :c, true, false, 'signed') RETURNING id"
                ),
                {"p": package_id, "c": contract_no},
            ).scalar()

        # The terms of the earlier contract (dates, advance, bonds, penalty) no longer apply.
        bind.execute(
            sa.text(
                "UPDATE contracts SET contract_no = :c, value = :v, signed_date = NULL, "
                "effective_date = :s, duration_days = :d, planned_end_date = :e, "
                "extended_end_date = NULL, end_date_override = true, contract_type = NULL, "
                "price_adjustment = false, advance_pct = NULL, advance_amount = NULL, "
                "performance_bond_pct = NULL, performance_bond_amount = NULL, "
                "penalty_rate_pct = NULL, penalty_unit = NULL, penalty_cap_pct = NULL, "
                "investor_account = NULL, data_quality_note = :note WHERE id = :id"
            ),
            {"c": contract_no, "v": value, "s": start, "d": days, "e": end, "note": note,
             "id": contract_id},
        )  # fmt: skip
        bind.execute(
            sa.text("DELETE FROM contract_parties WHERE contract_id = :id"), {"id": contract_id}
        )
        bind.execute(
            sa.text(
                "INSERT INTO contract_parties (id, contract_id, organization_id, role) "
                "VALUES (gen_random_uuid(), :c, :o, 'sole')"
            ),
            {"c": contract_id, "o": org_id},
        )


def downgrade() -> None:
    """The earlier values were mistakes in the listing; they are not restored."""
