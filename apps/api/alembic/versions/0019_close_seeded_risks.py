"""close the risks seeded before the tracking workbook became the source

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-31 15:00:00.000000

The ten Lam Dong risks R-001..R-010 were typed in by the seed. The workbook now carries the same
risks as `WB..` rows, so the seeded copies are closed (kept for history, not deleted).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEEDED_CODES = tuple(f"R-{n:03d}" for n in range(1, 11))


def upgrade() -> None:
    codes = ", ".join(f"'{code}'" for code in _SEEDED_CODES)
    op.execute(
        "UPDATE risks SET status = 'closed' "
        f"WHERE code IN ({codes}) AND source IN ('analysis', 'de_cuong') AND status <> 'closed'"
    )


def downgrade() -> None:
    # The previous status of each risk is not recorded, so a downgrade cannot restore it.
    pass
