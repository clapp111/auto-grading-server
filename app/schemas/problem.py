from pydantic import BaseModel, ConfigDict, Field

from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage
from app.schemas.common import Region


class ProblemCreateRequest(BaseModel):
    label: str = Field(max_length=50)
    type: ProblemType
    max_score: int = Field(ge=0)
    region: Region | None = None


class ProblemUpdateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    type: ProblemType | None = None
    max_score: int | None = Field(default=None, ge=0)
    region: Region | None = None
    problem_text: str | None = None
    language: ProgrammingLanguage | None = None


class ProblemResponse(BaseModel):
    problem_id: int
    exam_id: int
    label: str
    type: ProblemType
    max_score: int
    region: Region | None
    language: ProgrammingLanguage | None
    problem_text: str | None

    model_config = ConfigDict(from_attributes=True)
