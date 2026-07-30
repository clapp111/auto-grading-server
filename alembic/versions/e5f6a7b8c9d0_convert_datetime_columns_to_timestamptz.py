"""convert datetime columns to timestamptz

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_naive_timestamp(table_name: str, column_name: str) -> bool:
    """Return whether a PostgreSQL timestamp column still lacks timezone data."""
    column = next(
        column
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
        if column["name"] == column_name
    )
    return isinstance(column["type"], sa.DateTime) and not column["type"].timezone


def upgrade() -> None:
    op.alter_column(
        "exam",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    # Existing databases reached this revision with a naive timestamp. Fresh
    # installations receive timestamptz from revision 529137af94fc directly.
    if _is_naive_timestamp("exam", "updated_at"):
        op.alter_column(
            "exam",
            "updated_at",
            type_=sa.DateTime(timezone=True),
            postgresql_using="updated_at AT TIME ZONE 'UTC'",
        )

    op.alter_column(
        "job",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "started_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "completed_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "exam",
        "created_at",
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    # Revision 529137af94fc defines this column as timestamptz, so preserve
    # that type when downgrading only this conversion revision.

    op.alter_column(
        "job",
        "created_at",
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "started_at",
        type_=sa.DateTime(),
        postgresql_using="started_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "completed_at",
        type_=sa.DateTime(),
        postgresql_using="completed_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "job",
        "updated_at",
        type_=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
