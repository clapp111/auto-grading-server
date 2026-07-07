from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.layout_mode import LayoutMode
from app.enums.region_shape import RegionShape


class AnswerRegion(Base):
    __tablename__ = "answer_region"
    __table_args__ = (UniqueConstraint("answer_sheet_id", "problem_id", "layout_mode"),)

    answer_region_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_sheet_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("answer_sheet.answer_sheet_id", ondelete="CASCADE"), nullable=False)
    problem_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("problem.problem_id", ondelete="CASCADE"), nullable=False)
    shape: Mapped[RegionShape] = mapped_column(SAEnum(RegionShape), nullable=False)
    bbox_region: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    polygon_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    layout_mode: Mapped[LayoutMode] = mapped_column(SAEnum(LayoutMode), nullable=False)
    region_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
