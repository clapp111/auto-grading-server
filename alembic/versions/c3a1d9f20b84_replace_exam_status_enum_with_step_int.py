"""replace exam status enum with step int

Revision ID: c3a1d9f20b84
Revises: 11d636654806
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3a1d9f20b84'
down_revision: Union[str, None] = '11d636654806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('exam', sa.Column('step', sa.Integer(), nullable=False, server_default='0'))

    op.execute("""
        UPDATE exam SET step = CASE status
            WHEN 'DRAFT'    THEN 0
            WHEN 'SETUP'    THEN 1
            WHEN 'OCR'      THEN 5
            WHEN 'GRADING'  THEN 6
            WHEN 'DONE'     THEN 7
            ELSE 0
        END
    """)

    op.drop_column('exam', 'status')
    op.execute('DROP TYPE IF EXISTS examstatus')


def downgrade() -> None:
    op.execute("CREATE TYPE examstatus AS ENUM ('DRAFT', 'SETUP', 'OCR', 'GRADING', 'DONE')")
    op.add_column('exam', sa.Column('status', sa.Enum('DRAFT', 'SETUP', 'OCR', 'GRADING', 'DONE', name='examstatus'), nullable=False, server_default='DRAFT'))

    op.execute("""
        UPDATE exam SET status = CASE
            WHEN step = 0           THEN 'DRAFT'
            WHEN step BETWEEN 1 AND 4 THEN 'SETUP'
            WHEN step = 5           THEN 'OCR'
            WHEN step = 6           THEN 'GRADING'
            WHEN step = 7           THEN 'DONE'
            ELSE 'DRAFT'
        END::examstatus
    """)

    op.drop_column('exam', 'step')
