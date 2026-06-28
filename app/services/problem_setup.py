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
from app.schemas.problem import ProblemCreateRequest, ProblemResponse, ProblemUpdateRequest
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class ProblemSetupService:
    def __init__(self, problem_repo: ProblemRepository, exam_repo: ExamRepository, job_repo: JobRepository, storage: StorageClient):
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo
        self.storage = storage

    def _get_exam_or_raise(self, exam_id: int, member_id: int) -> Exam:
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return exam

    def _get_problem_or_raise(self, problem_id: int, member_id: int) -> Problem:
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise ProblemNotFoundError()
        return problem

    def issue_problem_sheet_url(self, exam_id: int, member_id: int, request: PresignedUrlRequest) -> PresignedUrlResponse:
        exam = self._get_exam_or_raise(exam_id, member_id)
        file_key = self.storage.generate_key(f"exams/{exam_id}/problem-sheet", request.file_name)
        self.exam_repo.update(exam, problem_sheet_file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)

    def create_problem(self, exam_id: int, member_id: int, request: ProblemCreateRequest) -> ProblemResponse:
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
                    "source": {"trigger": "auto", "endpoint": f"/api/v1/exams/{exam_id}/problems"},
                },
            )
            run_problem_ocr.delay(job.job_id)

        return ProblemResponse.model_validate(problem)

    def update_problem(self, problem_id: int, member_id: int, request: ProblemUpdateRequest) -> ProblemResponse:
        from app.workers.ocr_tasks import run_problem_ocr

        problem = self._get_problem_or_raise(problem_id, member_id)
        updates = request.model_dump(exclude_unset=True)
        if "region" in updates:
            updates["region"] = request.region.model_dump() if request.region else None
        problem = self.problem_repo.update(problem, **updates)

        if updates.get("region") is not None:
            job = self.job_repo.create(
                exam_id=problem.exam_id,
                type=JobType.PROBLEM_OCR,
                requested_by_member_id=member_id,
                problem_id=problem_id,
                input_json={
                    "scope": {"problemIds": [problem_id]},
                    "source": {"trigger": "auto", "endpoint": f"/api/v1/problems/{problem_id}"},
                },
            )
            run_problem_ocr.delay(job.job_id)

        return ProblemResponse.model_validate(problem)

    def list_problems(self, exam_id: int, member_id: int) -> list[ProblemResponse]:
        self._get_exam_or_raise(exam_id, member_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        return [ProblemResponse.model_validate(p) for p in problems]

    def delete_problem(self, problem_id: int, member_id: int) -> None:
        problem = self._get_problem_or_raise(problem_id, member_id)
        self.problem_repo.delete(problem)


def get_problem_setup_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ProblemSetupService:
    return ProblemSetupService(ProblemRepository(db), ExamRepository(db), JobRepository(db), storage)
