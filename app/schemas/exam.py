from datetime import datetime

from pydantic import BaseModel, Field

from app.enums.exam_status import ExamStatus
from app.schemas.common import CursorMeta


class ExamCursorMeta(CursorMeta):
    draft: int
    in_progress: int
    done: int


class ExamCreate(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=200)


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=200)


class ExamResponse(BaseModel):
    exam_id: int
    name: str
    description: str | None
    status: ExamStatus
    student_count: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
