"""add embedding vector columns

Revision ID: 7f6d4f5b3c21
Revises: 0a253879171d
Create Date: 2026-03-08 17:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f6d4f5b3c21"
down_revision: Union[str, Sequence[str], None] = "0a253879171d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE sku_notices ADD COLUMN embedding vector(1536)")
    op.add_column(
        "sku_notices",
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sku_notices", "embedding_updated_at")
    op.execute("ALTER TABLE sku_notices DROP COLUMN IF EXISTS embedding")
