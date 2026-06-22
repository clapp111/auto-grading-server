from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.enums.job_status import JobStatus
from app.enums.job_type import JobType


class JobStartedResponse(BaseModel):
    job_id: int
    status: JobStatus


class JobResponse(BaseModel):
    job_id: int
    exam_id: int
    problem_id: int | None
    requested_by_member_id: int
    retry_of_job_id: int | None

    type: JobType
    status: JobStatus

    input_json: dict[str, Any] | None
    progress_json: dict[str, Any] | None
    result_json: dict[str, Any] | None
    error_json: dict[str, Any] | None

    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
