from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExamMember(Base):
    __tablename__ = "exam_member"
    __table_args__ = (UniqueConstraint("exam_id", "member_id"),)

    exam_member_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    exam_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exam.exam_id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("member.member_id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
