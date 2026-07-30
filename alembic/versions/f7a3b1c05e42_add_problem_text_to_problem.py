"""add_problem_text_to_problem

Revision ID: f7a3b1c05e42
Revises: d6e4f5a93b21
Create Date: 2026-06-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a3b1c05e42"
down_revision: Union[str, None] = "d6e4f5a93b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("problem", sa.Column("problem_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("problem", "problem_text")
