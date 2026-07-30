from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ProblemNotFoundError,
    RubricNotFoundError,
)
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.rubric_source import RubricSource
from app.models.rubric import Rubric
from app.repositories.exam import ExamRepository
from app.repositories.grade import GradeRepository
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
        grade_repo: GradeRepository,
    ):
        self.rubric_repo = rubric_repo
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo
        self.grade_repo = grade_repo

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def get_rubric(self, problem_id: int, member_id: int) -> list[RubricResponse]:
        """문제의 채점 기준(루브릭) 목록을 조회한다.

        Args:
            problem_id: 조회할 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제의 채점 기준 목록

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        self._get_problem_or_raise(problem_id, member_id)
        rubrics = self.rubric_repo.list_by_problem(problem_id)
        return [RubricResponse.model_validate(r) for r in rubrics]

    def save_rubric(
        self, problem_id: int, member_id: int, request: RubricSaveRequest
    ) -> list[RubricResponse]:
        """문제의 채점 기준을 전달된 목록으로 통째로 교체한다.

        기존 채점 기준과 이미 매겨진 채점 결과를 모두 삭제한 뒤 새 기준을 저장한다.
        기준이 바뀌면 이전 채점이 무의미해지므로 함께 지운다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID
            request: 저장할 채점 기준 목록

        Returns:
            새로 저장된 채점 기준 목록

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        self.rubric_repo.delete_by_problem(problem_id)
        self.grade_repo.delete_by_problem(problem_id)
        criteria = [c.model_dump() for c in request.criteria]
        rubrics = self.rubric_repo.bulk_create(problem_id, criteria, RubricSource.HUMAN)
        self.exam_repo.touch(exam_id)
        return [RubricResponse.model_validate(r) for r in rubrics]

    def create_criterion(
        self, problem_id: int, member_id: int, request: RubricCreateRequest
    ) -> RubricResponse:
        """문제에 채점 기준 항목 하나를 추가한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID
            request: 기준 내용·배점·정렬 순서

        Returns:
            생성된 채점 기준 항목

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        rubric = self.rubric_repo.create(
            problem_id=problem_id,
            text=request.text,
            allocated_score=request.allocated_score,
            source=RubricSource.HUMAN,
            order_index=request.order_index,
        )
        self.exam_repo.touch(exam_id)
        return RubricResponse.model_validate(rubric)

    def update_criterion(
        self, rubric_id: int, member_id: int, request: RubricUpdateRequest
    ) -> RubricResponse:
        """채점 기준 항목을 수정한다.

        전송된 필드만 갱신한다.

        Args:
            rubric_id: 수정할 채점 기준 ID
            member_id: 요청한 사용자 ID
            request: 변경할 기준 필드 (미전송 필드는 무시)

        Returns:
            수정된 채점 기준 항목

        Raises:
            RubricNotFoundError: 기준이 없거나 접근 권한이 없는 경우
        """
        rubric, exam_id = self._get_rubric_or_raise(rubric_id, member_id)
        updates = request.model_dump(exclude_unset=True)
        rubric = self.rubric_repo.update(rubric, **updates)
        self.exam_repo.touch(exam_id)
        return RubricResponse.model_validate(rubric)

    def delete_criterion(self, rubric_id: int, member_id: int) -> None:
        """채점 기준 항목을 삭제한다.

        Args:
            rubric_id: 삭제할 채점 기준 ID
            member_id: 요청한 사용자 ID

        Raises:
            RubricNotFoundError: 기준이 없거나 접근 권한이 없는 경우
        """
        rubric, exam_id = self._get_rubric_or_raise(rubric_id, member_id)
        self.rubric_repo.delete(rubric)
        self.exam_repo.touch(exam_id)

    def suggest_rubric(self, problem_id: int, member_id: int) -> JobStartedResponse:
        """LLM 기반 채점 기준 제안 잡을 생성해 비동기로 실행한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        from app.workers.rubric_tasks import suggest_rubric_task

        problem = self._get_problem_or_raise(problem_id, member_id)

        job = self.job_repo.create(
            exam_id=problem.exam_id,
            type=JobType.RUBRIC_SUGGEST,
            requested_by_member_id=member_id,
            problem_id=problem_id,
            input_json={
                "scope": {"problemIds": [problem_id]},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/problems/{problem_id}/rubric/suggest",
                },
            },
        )
        suggest_rubric_task.delay(job.job_id)
        self.exam_repo.touch(problem.exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _get_problem_or_raise(self, problem_id: int, member_id: int):
        """문제를 조회하고, 없거나 접근 권한이 없으면 예외를 던진다.

        Args:
            problem_id: 조회할 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 문제

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_accessible(problem.exam_id, member_id)
        if not exam:
            raise ProblemNotFoundError()
        return problem

    def _get_rubric_or_raise(
        self, rubric_id: int, member_id: int
    ) -> tuple[Rubric, int]:
        """채점 기준을 조회하고, 접근 가능한 시험 ID와 함께 반환한다.

        기준·문제·시험 접근 권한을 차례로 확인하며, 하나라도 어긋나면 존재를 숨긴다.

        Args:
            rubric_id: 조회할 채점 기준 ID
            member_id: 요청한 사용자 ID

        Returns:
            채점 기준과 그것이 속한 시험 ID의 튜플

        Raises:
            RubricNotFoundError: 기준·문제가 없거나 접근 권한이 없는 경우
        """
        rubric = self.rubric_repo.get_by_id(rubric_id)
        if not rubric:
            raise RubricNotFoundError()
        problem = self.problem_repo.get_by_id(rubric.problem_id)
        if not problem:
            raise RubricNotFoundError()
        exam = self.exam_repo.get_accessible(problem.exam_id, member_id)
        if not exam:
            raise RubricNotFoundError()
        return rubric, problem.exam_id


def get_rubric_service(db: Session = Depends(get_db)) -> RubricService:
    return RubricService(
        RubricRepository(db),
        ProblemRepository(db),
        ExamRepository(db),
        JobRepository(db),
        GradeRepository(db),
    )
