from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, ProblemNotFoundError, RubricNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.rubric_source import RubricSource
from app.models.rubric import Rubric
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.problem import ProblemRepository
from app.repositories.rubric import RubricRepository
from app.schemas.job import JobStartedResponse
from app.schemas.rubric import (
    RubricCreateRequest,
    RubricResponse,
    RubricSaveRequest,
    RubricUpdateRequest,
)


class RubricService:
    def __init__(
        self,
        rubric_repo: RubricRepository,
        problem_repo: ProblemRepository,
        exam_repo: ExamRepository,
        job_repo: JobRepository,
    ):
        self.rubric_repo = rubric_repo
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo

    def _get_problem_or_raise(self, problem_id: int, member_id: int):
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise ProblemNotFoundError()
        return problem

    def _get_rubric_or_raise(self, rubric_id: int, member_id: int) -> Rubric:
        rubric = self.rubric_repo.get_by_id(rubric_id)
        if not rubric:
            raise RubricNotFoundError()
        problem = self.problem_repo.get_by_id(rubric.problem_id)
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise RubricNotFoundError()
        return rubric

    def get_rubric(self, problem_id: int, member_id: int) -> list[RubricResponse]:
        self._get_problem_or_raise(problem_id, member_id)
        rubrics = self.rubric_repo.list_by_problem(problem_id)
        return [RubricResponse.model_validate(r) for r in rubrics]

    def save_rubric(self, problem_id: int, member_id: int, request: RubricSaveRequest) -> list[RubricResponse]:
        self._get_problem_or_raise(problem_id, member_id)
        self.rubric_repo.delete_by_problem(problem_id)
        criteria = [c.model_dump() for c in request.criteria]
        rubrics = self.rubric_repo.bulk_create(problem_id, criteria, RubricSource.HUMAN)
        return [RubricResponse.model_validate(r) for r in rubrics]

    def create_criterion(self, problem_id: int, member_id: int, request: RubricCreateRequest) -> RubricResponse:
        self._get_problem_or_raise(problem_id, member_id)
        rubric = self.rubric_repo.create(
            problem_id=problem_id,
            text=request.text,
            allocated_score=request.allocated_score,
            source=RubricSource.HUMAN,
            order_index=request.order_index,
        )
        return RubricResponse.model_validate(rubric)

    def update_criterion(self, rubric_id: int, member_id: int, request: RubricUpdateRequest) -> RubricResponse:
        rubric = self._get_rubric_or_raise(rubric_id, member_id)
        updates = request.model_dump(exclude_unset=True)
        rubric = self.rubric_repo.update(rubric, **updates)
        return RubricResponse.model_validate(rubric)

    def delete_criterion(self, rubric_id: int, member_id: int) -> None:
        rubric = self._get_rubric_or_raise(rubric_id, member_id)
        self.rubric_repo.delete(rubric)

    def suggest_rubric(self, problem_id: int, member_id: int) -> JobStartedResponse:
        from app.workers.rubric_tasks import suggest_rubric_task

        problem = self._get_problem_or_raise(problem_id, member_id)

        job = self.job_repo.create(
            exam_id=problem.exam_id,
            type=JobType.RUBRIC_SUGGEST,
            requested_by_member_id=member_id,
            problem_id=problem_id,
            input_json={
                "scope": {"problemIds": [problem_id]},
                "source": {"trigger": "api", "endpoint": f"/api/v1/problems/{problem_id}/rubric/suggest"},
            },
        )
        suggest_rubric_task.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)


def get_rubric_service(db: Session = Depends(get_db)) -> RubricService:
    return RubricService(
        RubricRepository(db),
        ProblemRepository(db),
        ExamRepository(db),
        JobRepository(db),
    )
