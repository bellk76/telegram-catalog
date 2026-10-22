"""product idempotency key

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.create_unique_constraint(
        "uq_products_idempotency_key",
        "products",
        ["idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_products_idempotency_key", "products", type_="unique")
    op.drop_column("products", "idempotency_key")
