from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, ProblemNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.models.exam import Exam
from app.models.problem import Problem
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.problem import ProblemRepository
from app.schemas.job import JobStartedResponse
from app.schemas.problem import (
    ProblemCreateRequest,
    ProblemResponse,
    ProblemUpdateRequest,
)
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class ProblemService:
    def __init__(
        self,
        problem_repo: ProblemRepository,
        exam_repo: ExamRepository,
        job_repo: JobRepository,
        storage: StorageClient,
    ):
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo
        self.storage = storage

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def issue_problem_sheet_url(
        self, exam_id: int, member_id: int, request: PresignedUrlRequest
    ) -> PresignedUrlResponse:
        """문제지 업로드용 presigned URL을 발급하고 file key를 저장한다.

        업로드 전에 시험에 file key를 먼저 기록한다.

        Args:
            exam_id: 문제지를 올릴 시험 ID
            member_id: 요청한 사용자 ID
            request: 파일명과 content type

        Returns:
            업로드 URL과 저장된 file key

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self._get_exam_or_raise(exam_id, member_id)
        file_key = self.storage.generate_key(
            f"exams/{exam_id}/problem-sheet", request.file_name
        )
        self.exam_repo.update(exam, problem_sheet_file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)

    def create_problem(
        self, exam_id: int, member_id: int, request: ProblemCreateRequest
    ) -> ProblemResponse:
        """문제를 생성한다.

        영역(region)이 지정된 경우 문제 OCR 잡을 함께 생성해 비동기로 실행한다.

        Args:
            exam_id: 문제를 추가할 시험 ID
            member_id: 요청한 사용자 ID
            request: 문제 라벨·유형·배점·영역 정보

        Returns:
            생성된 문제 정보

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_problem_ocr

        self._get_exam_or_raise(exam_id, member_id)
        problem = self.problem_repo.create(
            exam_id=exam_id,
            label=request.label,
            type=request.type,
            max_score=request.max_score,
            region=request.region.model_dump() if request.region else None,
        )

        if request.region is not None:
            job = self.job_repo.create(
                exam_id=exam_id,
                type=JobType.PROBLEM_OCR,
                requested_by_member_id=member_id,
                problem_id=problem.problem_id,
                input_json={
                    "scope": {"problemIds": [problem.problem_id]},
                    "source": {
                        "trigger": "auto",
                        "endpoint": f"/api/v1/exams/{exam_id}/problems",
                    },
                },
            )
            run_problem_ocr.delay(job.job_id)

        self.exam_repo.touch(exam_id)
        return ProblemResponse.model_validate(problem)

    def update_problem(
        self, problem_id: int, member_id: int, request: ProblemUpdateRequest
    ) -> ProblemResponse:
        """문제를 수정한다.

        전송된 필드만 갱신하며, 영역(region)이 새로 지정되면 문제 OCR 잡을 다시 실행한다.

        Args:
            problem_id: 수정할 문제 ID
            member_id: 요청한 사용자 ID
            request: 변경할 문제 필드 (미전송 필드는 무시)

        Returns:
            수정된 문제 정보

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_problem_ocr

        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        updates = request.model_dump(exclude_unset=True)
        if "region" in updates:
            updates["region"] = request.region.model_dump() if request.region else None
        problem = self.problem_repo.update(problem, **updates)

        if updates.get("region") is not None:
            job = self.job_repo.create(
                exam_id=exam_id,
                type=JobType.PROBLEM_OCR,
                requested_by_member_id=member_id,
                problem_id=problem_id,
                input_json={
                    "scope": {"problemIds": [problem_id]},
                    "source": {
                        "trigger": "auto",
                        "endpoint": f"/api/v1/problems/{problem_id}",
                    },
                },
            )
            run_problem_ocr.delay(job.job_id)

        self.exam_repo.touch(exam_id)
        return ProblemResponse.model_validate(problem)

    def run_problem_ocr(self, problem_id: int, member_id: int) -> JobStartedResponse:
        """문제 영역 OCR 잡을 생성해 비동기로 실행한다.

        Args:
            problem_id: OCR을 실행할 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_problem_ocr

        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.PROBLEM_OCR,
            requested_by_member_id=member_id,
            problem_id=problem_id,
            input_json={
                "scope": {"problemIds": [problem_id]},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/problems/{problem_id}/ocr",
                },
            },
        )
        run_problem_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def list_problems(self, exam_id: int, member_id: int) -> list[ProblemResponse]:
        """시험의 문제 목록을 조회한다.

        Args:
            exam_id: 문제를 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            시험에 속한 문제 목록

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        self._get_exam_or_raise(exam_id, member_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        return [ProblemResponse.model_validate(p) for p in problems]

    def delete_problem(self, problem_id: int, member_id: int) -> None:
        """문제를 삭제한다.

        Args:
            problem_id: 삭제할 문제 ID
            member_id: 요청한 사용자 ID

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        self.problem_repo.delete(problem)
        self.exam_repo.touch(exam_id)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _get_exam_or_raise(self, exam_id: int, member_id: int) -> Exam:
        """접근 가능한 시험을 조회하고, 없으면 예외를 던진다.

        Args:
            exam_id: 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 시험

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        return exam

    def _get_problem_or_raise(self, problem_id: int, member_id: int) -> Problem:
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


def get_problem_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ProblemService:
    return ProblemService(
        ProblemRepository(db), ExamRepository(db), JobRepository(db), storage
    )
