from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.rubric_source import RubricSource

if TYPE_CHECKING:
    from app.models.problem import Problem


class Rubric(Base):
    __tablename__ = "rubric"

    rubric_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    allocated_score: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[RubricSource] = mapped_column(SAEnum(RubricSource), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    problem: Mapped["Problem"] = relationship(back_populates="rubrics")
