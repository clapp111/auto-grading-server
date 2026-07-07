from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.db.base import Base
from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage

if TYPE_CHECKING:
    from app.models.exam import Exam
    from app.models.model_answer import ModelAnswer
    from app.models.rubric import Rubric
    from app.models.answer_region import AnswerRegion
    from app.models.job import Job


class Problem(Base):
    __tablename__ = "problem"

    problem_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.exam_id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[ProblemType] = mapped_column(SAEnum(ProblemType), nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[ProgrammingLanguage | None] = mapped_column(SAEnum(ProgrammingLanguage), nullable=True)
    problem_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="problems")
    model_answer: Mapped["ModelAnswer | None"] = relationship(back_populates="problem", uselist=False, cascade="all, delete-orphan")
    rubrics: Mapped[list["Rubric"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    answer_regions: Mapped[list["AnswerRegion"]] = relationship(back_populates="problem", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="problem")
