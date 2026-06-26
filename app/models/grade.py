from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.grade_method import GradeMethod
from app.enums.grade_status import GradeStatus

if TYPE_CHECKING:
    from app.models.problem import Problem
    from app.models.student import Student


class Grade(Base):
    __tablename__ = "grade"
    __table_args__ = (UniqueConstraint("problem_id", "student_id"),)

    grade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id"), nullable=False)
    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student.student_id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[GradeStatus] = mapped_column(SAEnum(GradeStatus), nullable=False, default=GradeStatus.SUGGESTED)
    method: Mapped[GradeMethod] = mapped_column(SAEnum(GradeMethod), nullable=False)
    rubric_breakdown: Mapped[list | None] = mapped_column(JSON, nullable=True)

    problem: Mapped["Problem"] = relationship(back_populates="grades")
    student: Mapped["Student"] = relationship(back_populates="grades")
