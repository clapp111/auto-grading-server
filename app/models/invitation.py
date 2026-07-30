from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.invitation_status import InvitationStatus


class Invitation(Base):
    __tablename__ = "invitation"
    __table_args__ = (
        # 같은 사람에게 대기 중인 초대는 하나만. 거절/취소된 초대는 남겨두고 재초대할 수 있어야 하므로 부분 인덱스로 제한한다.
        Index(
            "uq_invitation_pending",
            "exam_id",
            "invitee_member_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    invitation_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    exam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exam.exam_id", ondelete="CASCADE"), nullable=False
    )
    inviter_member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("member.member_id", ondelete="CASCADE"), nullable=False
    )
    invitee_member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("member.member_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus), nullable=False, default=InvitationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
