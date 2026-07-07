from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage


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

