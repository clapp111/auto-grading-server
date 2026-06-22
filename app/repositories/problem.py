from sqlalchemy.orm import Session

from app.enums.problem_type import ProblemType
from app.enums.programming_language import ProgrammingLanguage
from app.models.problem import Problem


class ProblemRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, problem_id: int) -> Problem | None:
        return self.db.get(Problem, problem_id)

    def list_by_exam(self, exam_id: int) -> list[Problem]:
        return (
            self.db.query(Problem)
            .filter(Problem.exam_id == exam_id)
            .order_by(Problem.problem_id)
            .all()
        )

    def create(
        self,
        exam_id: int,
        label: str,
        type: ProblemType,
        max_score: int,
        region: dict | None = None,
    ) -> Problem:
        problem = Problem(exam_id=exam_id, label=label, type=type, max_score=max_score, region=region)
        self.db.add(problem)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def update(self, problem: Problem, **kwargs) -> Problem:
        for key, value in kwargs.items():
            setattr(problem, key, value)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def delete(self, problem: Problem) -> None:
        self.db.delete(problem)
        self.db.commit()
