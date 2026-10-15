"""drop the Gói 05 diary entry written from the draft inspection report

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-15 15:00:00.000000

The entry (client_id seed:g05-bbdk-v2) was taken from a draft and was inaccurate. The seed now
writes the one taken from the handover record 1310/BBBG-G05/TVGS-SGM (seed:g05-bbbg-1310).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM progress_logs WHERE client_id = 'seed:g05-bbdk-v2'")


def downgrade() -> None:
    """The deleted entry was wrong; it is not restored."""
