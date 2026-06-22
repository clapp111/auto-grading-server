from pydantic import BaseModel, ConfigDict, Field

from app.enums.rubric_source import RubricSource


class RubricCriterionItem(BaseModel):
    text: str = Field(max_length=500)
    allocated_score: int = Field(ge=0)


class RubricCreateRequest(BaseModel):
    text: str = Field(max_length=500)
    allocated_score: int = Field(ge=0)
    order_index: int


class RubricSaveRequest(BaseModel):
    criteria: list[RubricCriterionItem]


class RubricUpdateRequest(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    allocated_score: int | None = Field(default=None, ge=0)
    order_index: int | None = None


class RubricResponse(BaseModel):
    rubric_id: int
    problem_id: int
    text: str
    allocated_score: int
    source: RubricSource
    order_index: int

    model_config = ConfigDict(from_attributes=True)
