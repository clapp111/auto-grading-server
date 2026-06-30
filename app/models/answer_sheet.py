from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.sheet_status import SheetStatus

if TYPE_CHECKING:
    from app.models.answer_region import AnswerRegion
    from app.models.exam import Exam
    from app.models.job import Job
    from app.models.student import Student


class AnswerSheet(Base):
    __tablename__ = "answer_sheet"
    __table_args__ = (
        # studentId가 null이 아닐 때만 (exam_id, student_id) 유니크
        Index("uq_answer_sheet_exam_student", "exam_id", "student_id", unique=True,
              postgresql_where=text("student_id IS NOT NULL")),
    )

    answer_sheet_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.exam_id"), nullable=False)
    student_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("student.student_id"), nullable=True)
    file_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SheetStatus] = mapped_column(SAEnum(SheetStatus), nullable=False, default=SheetStatus.UNMATCHED)

    exam: Mapped["Exam"] = relationship(back_populates="answer_sheets")
    student: Mapped["Student | None"] = relationship(back_populates="answer_sheet")
    answer_regions: Mapped[list["AnswerRegion"]] = relationship(back_populates="answer_sheet")
    jobs: Mapped[list["Job"]] = relationship(back_populates="answer_sheet")
