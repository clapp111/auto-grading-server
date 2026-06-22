from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.layout_mode import LayoutMode
from app.enums.region_shape import RegionShape

if TYPE_CHECKING:
    from app.models.answer_sheet import AnswerSheet
    from app.models.problem import Problem
    from app.models.ocr_result import OCRResult


class AnswerRegion(Base):
    __tablename__ = "answer_region"
    __table_args__ = (UniqueConstraint("answer_sheet_id", "problem_id"),)

    answer_region_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_sheet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("answer_sheet.answer_sheet_id"), nullable=False)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id"), nullable=False)
    shape: Mapped[RegionShape] = mapped_column(SAEnum(RegionShape), nullable=False)
    bbox_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    polygon_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    layout_mode: Mapped[LayoutMode] = mapped_column(SAEnum(LayoutMode), nullable=False)

    answer_sheet: Mapped["AnswerSheet"] = relationship(back_populates="answer_regions")
    problem: Mapped["Problem"] = relationship(back_populates="answer_regions")
    ocr_result: Mapped["OCRResult | None"] = relationship(back_populates="answer_region", uselist=False)
