"""add exam_member and invitation

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exam_member',
        sa.Column('exam_member_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.BigInteger(), nullable=False),
        sa.Column('member_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exam.exam_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['member.member_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('exam_member_id'),
        sa.UniqueConstraint('exam_id', 'member_id'),
    )
    # UNIQUE(exam_id, member_id)의 선두 컬럼이 exam_id라 exam_id 조회는 커버되지만,
    # "내가 참여 중인 시험 목록"은 member_id 단독 조회라 별도 인덱스가 필요하다.
    op.create_index('ix_exam_member_member_id', 'exam_member', ['member_id'])

    op.create_table(
        'invitation',
        sa.Column('invitation_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.BigInteger(), nullable=False),
        sa.Column('inviter_member_id', sa.BigInteger(), nullable=False),
        sa.Column('invitee_member_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'ACCEPTED', 'DECLINED', 'CANCELED', name='invitationstatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['exam.exam_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inviter_member_id'], ['member.member_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invitee_member_id'], ['member.member_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('invitation_id'),
    )
    op.create_index('ix_invitation_exam_id', 'invitation', ['exam_id'])
    op.create_index('ix_invitation_invitee_member_id', 'invitation', ['invitee_member_id'])
    op.create_index('ix_invitation_inviter_member_id', 'invitation', ['inviter_member_id'])
    # 대기 중인 초대는 (시험, 초대받는 사람)당 하나만 허용. 거절/취소 이력은 남기고 재초대를 허용하기 위해 부분 인덱스로 건다.
    op.create_index(
        'uq_invitation_pending', 'invitation', ['exam_id', 'invitee_member_id'],
        unique=True, postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index('uq_invitation_pending', table_name='invitation')
    op.drop_index('ix_invitation_inviter_member_id', table_name='invitation')
    op.drop_index('ix_invitation_invitee_member_id', table_name='invitation')
    op.drop_index('ix_invitation_exam_id', table_name='invitation')
    op.drop_table('invitation')
    sa.Enum(name='invitationstatus').drop(op.get_bind())

    op.drop_index('ix_exam_member_member_id', table_name='exam_member')
    op.drop_table('exam_member')
