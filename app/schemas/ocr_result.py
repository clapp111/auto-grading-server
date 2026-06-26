from pydantic import BaseModel

from app.enums.ocr_status import OCRStatus
from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage
from app.enums.region_shape import RegionShape
from app.schemas.common import Point, Region


class OcrResultUpdateRequest(BaseModel):
    text: str | None = None
    marked_choice: int | None = None


class OcrResultResponse(BaseModel):
    ocr_result_id: int
    problem_id: int
    problem_label: str
    problem_type: ProblemType
    problem_language: ProgrammingLanguage | None
    text: str | None
    marked_choice: int | None
    status: OCRStatus
    answer_sheet_id: int
    shape: RegionShape
    bbox_region: Region | None
    polygon_points: list[Point] | None

    model_config = {"from_attributes": True}


class StudentOcrProgressItem(BaseModel):
    student_id: int
    name: str
    student_no: str
    confirmed_count: int
    total_count: int
    percent: int


class OcrProgressResponse(BaseModel):
    confirmed_student_count: int
    total_student_count: int
    students: list[StudentOcrProgressItem]
