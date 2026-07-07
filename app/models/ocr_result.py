from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.ocr_status import OCRStatus


class OCRResult(Base):
    __tablename__ = "ocr_result"

    ocr_result_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    answer_region_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("answer_region.answer_region_id", ondelete="CASCADE"), nullable=False, unique=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_choice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[OCRStatus] = mapped_column(SAEnum(OCRStatus), nullable=False, default=OCRStatus.RAW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
