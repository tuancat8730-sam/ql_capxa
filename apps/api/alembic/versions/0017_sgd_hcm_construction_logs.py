"""SGD-HCM: load the construction logs of 25/09 – 01/10 and 09/10 – 15/10/2026

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-17 14:30:00.000000

Source: the contractor's weekly construction logs (data_documents/SGD_TPHCM/nhat_ky_thi_cong).
The seed carries the same data for a fresh database; this migration brings an existing one in
line. Only the weeks that have no log are added, so a log edited in the application is kept.
"""

from collections.abc import Sequence

from alembic import op
from app.seed.sgd_hcm_logs import apply_logs

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_logs(op.get_bind())


def downgrade() -> None:
    """The logs may have been edited in the application; they go with the tables in 0016."""
