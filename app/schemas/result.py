from pydantic import BaseModel


class ScoreDistribution(BaseModel):
    range_label: str
    count: int


class ResultSummary(BaseModel):
    exam_id: str
    total_students: int
    average_score: float
    max_score: float
    min_score: float
    std_dev: float
    distribution: list[ScoreDistribution]


class ProblemScore(BaseModel):
    problem_id: str
    problem_number: int
    score: float
    max_score: float


class StudentResult(BaseModel):
    student_id: str
    name: str
    student_number: str
    total_score: float
    max_total_score: float
    problem_scores: list[ProblemScore]
