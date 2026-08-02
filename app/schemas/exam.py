from datetime import datetime

from pydantic import BaseModel, Field

from app.enums.layout_mode import LayoutMode
from app.schemas.common import CursorMeta


class ExamCursorMeta(CursorMeta):
    draft: int
    in_progress: int
    done: int


class ExamCreateRequest(BaseModel):
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=200)


class ExamUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=200)
    layout_mode: LayoutMode | None = None


class ExamAdvanceRequest(BaseModel):
    from_step: int = Field(ge=0, le=6)


class ExamResponse(BaseModel):
    exam_id: int
    is_owner: bool
    name: str
    description: str | None
    step: int
    layout_mode: LayoutMode
    student_count: int
    problem_sheet_url: str | None = None
    model_answer_url: str | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
