"""init schema

Revision ID: 0a253879171d
Revises: 
Create Date: 2026-03-07 22:17:32.653441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a253879171d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sku_notices",
        sa.Column("source_notice_id", sa.BigInteger(), nullable=False),
        sa.Column("detail_url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("author_org", sa.String(length=100), nullable=True),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("list_number", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("attachments", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_notice_id", name="uq_sku_notices_source_notice_id"),
    )
    op.create_index("ix_sku_notices_category", "sku_notices", ["category"], unique=False)
    op.create_index("ix_sku_notices_posted_date", "sku_notices", ["posted_date"], unique=False)
    op.create_index("ix_sku_notices_status", "sku_notices", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sku_notices_status", table_name="sku_notices")
    op.drop_index("ix_sku_notices_posted_date", table_name="sku_notices")
    op.drop_index("ix_sku_notices_category", table_name="sku_notices")
    op.drop_table("sku_notices")
