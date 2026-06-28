from datetime import datetime

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.exam_status import ExamStatus
from app.enums.layout_mode import LayoutMode

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.problem import Problem
    from app.models.student import Student
    from app.models.answer_sheet import AnswerSheet
    from app.models.job import Job


class Exam(Base):
    __tablename__ = "exam"

    exam_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("member.member_id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    problem_sheet_file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    model_answer_file_key: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[ExamStatus] = mapped_column(SAEnum(ExamStatus), nullable=False, default=ExamStatus.DRAFT)
    layout_mode: Mapped[LayoutMode] = mapped_column(SAEnum(LayoutMode), nullable=False, default=LayoutMode.FIXED)
    student_name_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    student_no_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, onupdate=func.now())

    member: Mapped["Member"] = relationship(back_populates="exams")
    problems: Mapped[list["Problem"]] = relationship(back_populates="exam")
    students: Mapped[list["Student"]] = relationship(back_populates="exam")
    answer_sheets: Mapped[list["AnswerSheet"]] = relationship(back_populates="exam")
    jobs: Mapped[list["Job"]] = relationship(back_populates="exam")
