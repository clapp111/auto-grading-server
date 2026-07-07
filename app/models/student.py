from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Student(Base):
    __tablename__ = "student"
    __table_args__ = (UniqueConstraint("exam_id", "student_no"),)

    student_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam.exam_id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    student_no: Mapped[str] = mapped_column(String, nullable=False)
