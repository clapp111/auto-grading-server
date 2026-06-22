from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, ProblemNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.problem_type import ProblemType
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.models.problem import Problem
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.model_answer import ModelAnswerRepository
from app.repositories.problem import ProblemRepository
from app.schemas.job import JobStartedResponse
from app.schemas.model_answer import ModelAnswerOcrRequest, ModelAnswerResponse, ModelAnswerUpdateRequest
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class ModelAnswerService:
    def __init__(
        self,
        model_answer_repo: ModelAnswerRepository,
        problem_repo: ProblemRepository,
        exam_repo: ExamRepository,
        job_repo: JobRepository,
        storage: StorageClient,
    ):
        self.model_answer_repo = model_answer_repo
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo
        self.storage = storage

    def _get_problem_or_raise(self, problem_id: int, member_id: int) -> Problem:
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise ProblemNotFoundError()
        return problem

    def issue_model_answer_url(self, exam_id: int, member_id: int, request: PresignedUrlRequest) -> PresignedUrlResponse:
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        file_key = self.storage.generate_key(f"exams/{exam_id}/model-answer", request.file_name)
        self.exam_repo.update(exam, model_answer_file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)

    def run_ocr(self, problem_id: int, member_id: int, request: ModelAnswerOcrRequest) -> JobStartedResponse:
        from app.workers.ocr_tasks import run_model_answer_ocr

        problem = self._get_problem_or_raise(problem_id, member_id)

        if request.language is not None:
            self.problem_repo.update(problem, language=request.language)

        model_answer = self.model_answer_repo.get_or_create(problem_id)
        self.model_answer_repo.update(model_answer, region=request.region.model_dump())

        job = self.job_repo.create(
            exam_id=problem.exam_id,
            type=JobType.MODEL_ANSWER_OCR,
            requested_by_member_id=member_id,
            problem_id=problem_id,
            input_json={
                "scope": {"problemIds": [problem_id]},
                "source": {"trigger": "api", "endpoint": f"/api/v1/problems/{problem_id}/model-answer/ocr"},
            },
        )
        run_model_answer_ocr.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def list_model_answers(self, exam_id: int, member_id: int) -> list[ModelAnswerResponse]:
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        problems = self.problem_repo.list_by_exam(exam_id)
        problem_ids = [p.problem_id for p in problems]
        ma_map = self.model_answer_repo.map_by_problem_ids(problem_ids)
        result = []
        for problem in problems:
            ma = ma_map.get(problem.problem_id)
            if ma:
                result.append(ModelAnswerResponse.model_validate(ma))
            else:
                result.append(ModelAnswerResponse(
                    model_answer_id=None,
                    problem_id=problem.problem_id,
                    correct_choice=None,
                    choice_count=None,
                    accepted_answers=None,
                    model_answer_text=None,
                    region=None,
                ))
        return result

    def update_model_answer(self, problem_id: int, member_id: int, request: ModelAnswerUpdateRequest) -> ModelAnswerResponse:
        problem = self._get_problem_or_raise(problem_id, member_id)
        model_answer = self.model_answer_repo.get_or_create(problem_id)
        updates = _build_updates(problem.type, request)
        model_answer = self.model_answer_repo.update(model_answer, **updates)
        return ModelAnswerResponse.model_validate(model_answer)


def _build_updates(problem_type: ProblemType, request: ModelAnswerUpdateRequest) -> dict:
    if problem_type == ProblemType.MULTIPLE_CHOICE:
        return {k: v for k, v in {
            "correct_choice": request.correct_choice,
            "choice_count": request.choice_count,
        }.items() if v is not None}

    if problem_type == ProblemType.SHORT_ANSWER:
        return {"accepted_answers": request.accepted_answers} if request.accepted_answers is not None else {}

    if problem_type in (ProblemType.DESCRIPTIVE, ProblemType.CODING):
        updates = {}
        if request.model_answer_text is not None:
            updates["model_answer_text"] = request.model_answer_text
        if request.region is not None:
            updates["region"] = request.region.model_dump()
        return updates

    return {}


def get_model_answer_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ModelAnswerService:
    return ModelAnswerService(
        ModelAnswerRepository(db),
        ProblemRepository(db),
        ExamRepository(db),
        JobRepository(db),
        storage,
    )
