"""add_problem_ocr_to_jobtype

Revision ID: a1b2c3d4e5f6
Revises: f7a3b1c05e42
Create Date: 2026-06-28 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f7a3b1c05e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'PROBLEM_OCR'")


def downgrade() -> None:
    # PostgreSQL은 enum 값 삭제를 지원하지 않으므로 downgrade 불가
    pass
