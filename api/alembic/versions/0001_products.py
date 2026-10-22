"""products

Revision ID: 0001
Revises:
Create Date: 2026-10-21

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("image_key", sa.Text(), nullable=False),
        sa.Column("image_content_type", sa.String(100), nullable=False),
        sa.Column("image_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("image_key", name="uq_products_image_key"),
        sa.CheckConstraint("image_size > 0", name="image_size_positive"),
    )
    op.create_index("ix_products_created_at", "products", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_products_created_at", table_name="products")
    op.drop_table("products")

