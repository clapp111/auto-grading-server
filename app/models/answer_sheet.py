from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.sheet_status import SheetStatus


class AnswerSheet(Base):
    __tablename__ = "answer_sheet"
    __table_args__ = (
        Index("uq_answer_sheet_exam_student", "exam_id", "student_id", unique=True,
              postgresql_where=text("student_id IS NOT NULL")),
    )

    answer_sheet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.exam_id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("student.student_id", ondelete="SET NULL"), nullable=True)
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SheetStatus] = mapped_column(SAEnum(SheetStatus), nullable=False, default=SheetStatus.UNMATCHED)
