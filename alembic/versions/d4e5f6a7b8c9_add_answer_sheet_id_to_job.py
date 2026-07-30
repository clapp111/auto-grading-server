"""add answer_sheet_id to job

Revision ID: d4e5f6a7b8c9
Revises: c3a1d9f20b84
Create Date: 2026-06-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3a1d9f20b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job", sa.Column("answer_sheet_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_job_answer_sheet_id",
        "job",
        "answer_sheet",
        ["answer_sheet_id"],
        ["answer_sheet_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_answer_sheet_id", "job", type_="foreignkey")
    op.drop_column("job", "answer_sheet_id")
