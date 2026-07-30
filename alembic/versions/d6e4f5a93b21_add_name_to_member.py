"""add_name_to_member

Revision ID: d6e4f5a93b21
Revises: c5d2e3f84a12
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6e4f5a93b21"
down_revision: str | None = "c5d2e3f84a12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "member", sa.Column("name", sa.String(), nullable=False, server_default="")
    )
    op.alter_column("member", "name", server_default=None)


def downgrade() -> None:
    op.drop_column("member", "name")
