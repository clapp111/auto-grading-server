from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelAnswer(Base):
    __tablename__ = "model_answer"

    model_answer_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id", ondelete="CASCADE"), nullable=False, unique=True)
    correct_choice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    choice_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accepted_answers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
