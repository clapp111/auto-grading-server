from pydantic import BaseModel

from app.enums.grade_method import GradeMethod
from app.enums.grade_status import GradeStatus
from app.enums.problem_type import ProblemType


class RubricResultItem(BaseModel):
    rubric_id: int
    text: str
    allocated_score: int
    satisfied: bool


class RubricUpdateItem(BaseModel):
    rubric_id: int
    satisfied: bool


class GradeResponse(BaseModel):
    grade_id: int
    student_id: int
    student_name: str
    student_no: str
    score: int
    max_score: int
    comment: str | None
    status: GradeStatus
    method: GradeMethod
    rubric_breakdown: list[RubricResultItem] | None
    ocr_text: str | None
    marked_choice: int | None
    model_answer_text: str | None

    model_config = {"from_attributes": True}

class GradeCreateRequest(BaseModel):
    score: int

class GradeUpdateRequest(BaseModel):
    score: int | None = None
    comment: str | None = None
    rubric_breakdown: list[RubricUpdateItem] | None = None


class GradeBulkConfirmResponse(BaseModel):
    confirmed_count: int


class ProblemGradingItem(BaseModel):
    problem_id: int
    label: str
    type: ProblemType
    max_score: int
    confirmed_count: int
    total_count: int
    percent: int


class GradingProgressResponse(BaseModel):
    confirmed_count: int
    total_count: int
    problems: list[ProblemGradingItem]
