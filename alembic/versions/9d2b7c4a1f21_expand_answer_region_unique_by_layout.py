"""expand answer_region unique by layout mode

Revision ID: 9d2b7c4a1f21
Revises: b8c3d2e1f0a9
Create Date: 2026-06-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d2b7c4a1f21"
down_revision: Union[str, Sequence[str], None] = "b8c3d2e1f0a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "answer_region_answer_sheet_id_problem_id_key",
        "answer_region",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_answer_region_sheet_problem_layout",
        "answer_region",
        ["answer_sheet_id", "problem_id", "layout_mode"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_answer_region_sheet_problem_layout",
        "answer_region",
        type_="unique",
    )
    op.create_unique_constraint(
        "answer_region_answer_sheet_id_problem_id_key",
        "answer_region",
        ["answer_sheet_id", "problem_id"],
    )
