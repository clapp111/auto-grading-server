"""add_rubric_breakdown_to_grade

Revision ID: c5d2e3f84a12
Revises: b3f1a2c94d01
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5d2e3f84a12'
down_revision: Union[str, None] = 'b3f1a2c94d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('grade', sa.Column('rubric_breakdown', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('grade', 'rubric_breakdown')
