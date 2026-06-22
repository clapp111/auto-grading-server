from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.ocr_status import OCRStatus

if TYPE_CHECKING:
    from app.models.answer_region import AnswerRegion


class OCRResult(Base):
    __tablename__ = "ocr_result"

    ocr_result_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_region_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("answer_region.answer_region_id"), nullable=False, unique=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_choice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[OCRStatus] = mapped_column(SAEnum(OCRStatus), nullable=False, default=OCRStatus.RAW)

    answer_region: Mapped["AnswerRegion"] = relationship(back_populates="ocr_result")
