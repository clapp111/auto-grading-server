"""add_layout_mode_to_exam

Revision ID: b3f1a2c94d01
Revises: e2c24a7f9577
Create Date: 2026-06-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3f1a2c94d01"
down_revision: Union[str, None] = "a2e5b9c82335"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exam",
        sa.Column(
            "layout_mode",
            sa.Enum("FIXED", "FREE", name="layoutmode", create_type=False),
            nullable=False,
            server_default="FIXED",
        ),
    )


def downgrade() -> None:
    op.drop_column("exam", "layout_mode")
    # layoutmode enum 타입은 answer_region 테이블에서 계속 사용하므로 삭제하지 않음
