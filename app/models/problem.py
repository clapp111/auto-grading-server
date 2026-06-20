from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage


class Problem(Base):
    __tablename__ = "problem"

    problem_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.exam_id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[ProblemType] = mapped_column(SAEnum(ProblemType), nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[ProgrammingLanguage | None] = mapped_column(SAEnum(ProgrammingLanguage), nullable=True)

    exam: Mapped["Exam"] = relationship(back_populates="problems")
    model_answer: Mapped["ModelAnswer | None"] = relationship(back_populates="problem", uselist=False)
    rubrics: Mapped[list["Rubric"]] = relationship(back_populates="problem")
    answer_regions: Mapped[list["AnswerRegion"]] = relationship(back_populates="problem")
    grades: Mapped[list["Grade"]] = relationship(back_populates="problem")
    jobs: Mapped[list["Job"]] = relationship(back_populates="problem")
