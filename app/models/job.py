from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.enums.job_status import JobStatus
from app.enums.job_type import JobType


class Job(Base):
    __tablename__ = "job"

    # 식별 / 관계
    job_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exam.exam_id", ondelete="SET NULL"), nullable=True)
    problem_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("problem.problem_id", ondelete="SET NULL"), nullable=True)
    answer_sheet_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("answer_sheet.answer_sheet_id", ondelete="SET NULL"), nullable=True)
    requested_by_member_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("member.member_id", ondelete="SET NULL"), nullable=True)
    retry_of_job_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("job.job_id", ondelete="SET NULL"), nullable=True)

    # 유형 / 상태
    type: Mapped[JobType] = mapped_column(SAEnum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), nullable=False, default=JobStatus.PENDING)

    # 입력 범위(무엇을 대상으로 돌렸는가?)
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 진행률(현재 진행 상황을 담는 용도)
    progress_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 결과(요약과 결과 참조를 담는 용도)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # 실패 정보
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Celery 연동
    celery_task_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # 중복 방지(같은 요청 중복 생성 방지용)
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)

    # 시각 정보
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())

