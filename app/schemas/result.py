from pydantic import BaseModel

from app.enums.grade_status import GradeStatus
from app.schemas.grade import GradeResponse


class ProblemHeader(BaseModel):
    problem_id: int
    label: str
    max_score: int


class ProblemScoreItem(BaseModel):
    problem_id: int
    score: int | None
    status: GradeStatus | None


class StudentScoreItem(BaseModel):
    student_id: int
    name: str
    student_no: str
    total_score: int
    max_total_score: int
    problem_scores: list[ProblemScoreItem]


class ExamResultResponse(BaseModel):
    exam_id: int
    title: str
    problems: list[ProblemHeader]
    students: list[StudentScoreItem]


class ScoreBandItem(BaseModel):
    range_label: str
    count: int


class ProblemStatItem(BaseModel):
    problem_id: int
    label: str
    max_score: int
    average_score: float


class ExamStatisticsResponse(BaseModel):
    total_students: int
    fully_graded_count: int
    average_score: float
    highest_score: int
    lowest_score: int
    score_distribution: list[ScoreBandItem]
    problem_stats: list[ProblemStatItem]


class StudentDetailResultResponse(BaseModel):
    student_id: int
    name: str
    student_no: str
    total_score: int
    max_total_score: int
    grades: list[GradeResponse]
