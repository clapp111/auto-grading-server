from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.layout_mode import LayoutMode


class Exam(Base):
    __tablename__ = "exam"

    exam_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("member.member_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    problem_sheet_file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    model_answer_file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layout_mode: Mapped[LayoutMode] = mapped_column(
        SAEnum(LayoutMode), nullable=False, default=LayoutMode.FIXED
    )
    student_name_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    student_no_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )
