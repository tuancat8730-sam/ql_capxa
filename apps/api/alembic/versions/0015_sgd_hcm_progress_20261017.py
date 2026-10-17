"""SGD-HCM: load the progress, weekly reports, risks and open decisions exported on 17/10/2026

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-17 10:00:00.000000

Source: data_documents/SGD_TPHCM/data_updated_20261017.md (up to the contractor's report for
09/10 – 15/10/2026). The seed carries the same data for a fresh database; this migration brings
an existing one in line. Rows are upserted by task code, report week, risk code and decision
number; an open decision that someone already settled keeps its status.
"""

from collections.abc import Sequence

from alembic import op
from app.seed.sgd_hcm_progress import apply_progress

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_progress(op.get_bind())


def downgrade() -> None:
    """The earlier values were entered by hand in the application; they are not restored."""
