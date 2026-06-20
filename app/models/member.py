from sqlalchemy import BigInteger, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.position import Position
from app.enums.role import Role


class Member(Base):
    __tablename__ = "member"

    member_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    profile_key: Mapped[str | None] = mapped_column(String, nullable=True)
    affiliation: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[Position] = mapped_column(SAEnum(Position), nullable=False)
    role: Mapped[Role] = mapped_column(SAEnum(Role), nullable=False)

    exams: Mapped[list["Exam"]] = relationship(back_populates="member")
