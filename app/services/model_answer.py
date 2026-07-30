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
from app.schemas.model_answer import (
    ModelAnswerOcrRequest,
    ModelAnswerResponse,
    ModelAnswerUpdateRequest,
)
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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def issue_model_answer_url(
        self, exam_id: int, member_id: int, request: PresignedUrlRequest
    ) -> PresignedUrlResponse:
        """모범답안 파일 업로드용 presigned URL을 발급하고 file key를 저장한다.

        Args:
            exam_id: 모범답안을 올릴 시험 ID
            member_id: 요청한 사용자 ID
            request: 파일명과 content type

        Returns:
            업로드 URL과 저장된 file key

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        file_key = self.storage.generate_key(
            f"exams/{exam_id}/model-answer", request.file_name
        )
        self.exam_repo.update(exam, model_answer_file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)

    def run_ocr(
        self, problem_id: int, member_id: int, request: ModelAnswerOcrRequest
    ) -> JobStartedResponse:
        """모범답안 영역 OCR 잡을 생성해 비동기로 실행한다.

        요청에 언어가 있으면 문제의 언어를 갱신하고, 모범답안 레코드에 OCR 영역을 저장한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID
            request: OCR 영역과 (선택) 프로그래밍 언어

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_model_answer_ocr

        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id

        if request.language is not None:
            self.problem_repo.update(problem, language=request.language)

        model_answer = self.model_answer_repo.get_or_create(problem_id)
        self.model_answer_repo.update(model_answer, region=request.region.model_dump())

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.MODEL_ANSWER_OCR,
            requested_by_member_id=member_id,
            problem_id=problem_id,
            input_json={
                "scope": {"problemIds": [problem_id]},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/problems/{problem_id}/model-answer/ocr",
                },
            },
        )
        run_model_answer_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def list_model_answers(
        self, exam_id: int, member_id: int
    ) -> list[ModelAnswerResponse]:
        """시험의 모든 문제에 대한 모범답안 목록을 조회한다.

        모범답안이 아직 없는 문제는 빈 응답(모든 필드 `None`)으로 채워 문제 순서대로 반환한다.

        Args:
            exam_id: 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제별 모범답안 목록 (미작성 문제 포함)

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
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
                result.append(
                    ModelAnswerResponse(
                        model_answer_id=None,
                        problem_id=problem.problem_id,
                        correct_choice=None,
                        choice_count=None,
                        accepted_answers=None,
                        model_answer_text=None,
                        region=None,
                    )
                )
        return result

    def update_model_answer(
        self, problem_id: int, member_id: int, request: ModelAnswerUpdateRequest
    ) -> ModelAnswerResponse:
        """모범답안을 수정한다.

        문제 유형에 따라 반영할 필드가 달라진다(`_build_updates` 참고).

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID
            request: 문제 유형별 모범답안 필드

        Returns:
            수정된 모범답안 정보

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        model_answer = self.model_answer_repo.get_or_create(problem_id)
        updates = _build_updates(problem.type, request)
        model_answer = self.model_answer_repo.update(model_answer, **updates)
        self.exam_repo.touch(exam_id)
        return ModelAnswerResponse.model_validate(model_answer)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

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


def _build_updates(
    problem_type: ProblemType, request: ModelAnswerUpdateRequest
) -> dict:
    """문제 유형별로 모범답안 갱신 필드를 추린다.

    객관식은 정답 선택지·선택지 수, 단답형은 허용 답안, 서술형·코딩은 모범답안 텍스트와
    영역만 반영한다. 미전송(`None`) 필드는 제외한다.

    Args:
        problem_type: 대상 문제 유형
        request: 모범답안 수정 요청

    Returns:
        유형에 맞게 추려진 갱신 필드 딕셔너리
    """
    if problem_type == ProblemType.MULTIPLE_CHOICE:
        return {
            k: v
            for k, v in {
                "correct_choice": request.correct_choice,
                "choice_count": request.choice_count,
            }.items()
            if v is not None
        }

    if problem_type == ProblemType.SHORT_ANSWER:
        return (
            {"accepted_answers": request.accepted_answers}
            if request.accepted_answers is not None
            else {}
        )

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
