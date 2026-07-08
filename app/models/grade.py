from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.grade_method import GradeMethod
from app.enums.grade_status import GradeStatus


class Grade(Base):
    __tablename__ = "grade"
    __table_args__ = (UniqueConstraint("problem_id", "student_id"),)

    grade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[GradeStatus] = mapped_column(SAEnum(GradeStatus), nullable=False, default=GradeStatus.SUGGESTED)
    method: Mapped[GradeMethod] = mapped_column(SAEnum(GradeMethod), nullable=False)
    rubric_breakdown: Mapped[list | None] = mapped_column(JSON, nullable=True)
