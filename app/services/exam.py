from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, ExamStepConflictError
from app.db.session import get_db
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.infrastructure.storage.url import get_file_url
from app.models.exam import Exam
from app.repositories.exam import ExamRepository
from app.repositories.student import StudentRepository
from app.schemas.exam import (
    ExamCreateRequest,
    ExamCursorMeta,
    ExamResponse,
    ExamUpdateRequest,
)


class ExamService:
    def __init__(
        self,
        repo: ExamRepository,
        student_repo: StudentRepository,
        storage: StorageClient,
    ):
        self.repo = repo
        self.student_repo = student_repo
        self.storage = storage

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def list_exams(
        self,
        member_id: int,
        cursor: str | None,
        size: int,
        search: str | None,
        step: int | None,
    ) -> tuple[list[ExamResponse], ExamCursorMeta]:
        """사용자가 접근 가능한 시험 목록을 커서 기반으로 조회한다.

        소유하거나 참여 중인 시험을 대상으로 하며, 단계별 개수(draft/in_progress/done)를
        메타에 함께 담는다.

        Args:
            member_id: 조회를 요청한 사용자 ID
            cursor: 이전 페이지 마지막 시험 ID 커서 (첫 페이지는 `None`)
            size: 한 페이지에 담을 최대 개수
            search: 시험명 검색어
            step: 특정 진행 단계로 필터링할 값

        Returns:
            시험 목록과 커서 페이지네이션 메타
        """
        cursor_id = int(cursor) if cursor else None
        rows = self.repo.list_by_member(member_id, cursor_id, size, search, step)

        has_more = len(rows) > size
        items = rows[:size]
        next_cursor = str(items[-1].exam_id) if has_more else None

        counts = self.repo.count_by_step(member_id)
        meta = ExamCursorMeta(
            next_cursor=next_cursor,
            has_more=has_more,
            draft=counts["draft"],
            in_progress=counts["in_progress"],
            done=counts["done"],
        )
        student_count_map = self.student_repo.count_by_exams([e.exam_id for e in items])
        return [
            self._to_response(e, student_count_map.get(e.exam_id, 0)) for e in items
        ], meta

    def create_exam(self, member_id: int, request: ExamCreateRequest) -> ExamResponse:
        """새 시험을 생성한다.

        Args:
            member_id: 시험을 소유할 사용자 ID
            request: 시험명과 설명

        Returns:
            생성된 시험 정보
        """
        exam = self.repo.create(
            member_id=member_id,
            name=request.name,
            description=request.description,
        )
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def get_exam(self, exam_id: int, member_id: int) -> ExamResponse:
        """시험을 단건 조회한다.

        Args:
            exam_id: 조회할 시험 ID
            member_id: 조회를 요청한 사용자 ID

        Returns:
            조회된 시험 정보

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def update_exam(
        self, exam_id: int, member_id: int, request: ExamUpdateRequest
    ) -> ExamResponse:
        """시험 정보를 수정한다.

        전송된 필드만 갱신한다.

        Args:
            exam_id: 수정할 시험 ID
            member_id: 수정을 요청한 사용자 ID
            request: 변경할 시험 필드 (미전송 필드는 무시)

        Returns:
            수정된 시험 정보

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        updates = request.model_dump(exclude_unset=True)
        exam = self.repo.update(exam, **updates)
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def delete_exam(self, exam_id: int, member_id: int) -> None:
        """시험을 삭제한다.

        소유자만 삭제할 수 있으며, 연결된 S3 파일(문제지·모범답안·답안지)도 함께 제거한다.

        Args:
            exam_id: 삭제할 시험 ID
            member_id: 삭제를 요청한 사용자 ID

        Raises:
            ExamNotFoundError: 시험이 없거나 소유자가 아닌 경우
        """
        # 시험 삭제는 참여자에게 허용하지 않는다.
        exam = self.repo.get_owned(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()

        s3_keys = self.repo.get_answer_sheet_file_keys(exam_id)
        if exam.problem_sheet_file_key:
            s3_keys.append(exam.problem_sheet_file_key)
        if exam.model_answer_file_key:
            s3_keys.append(exam.model_answer_file_key)

        self.repo.delete(exam_id)

        for key in s3_keys:
            self.storage.delete(key)

    def advance_step(
        self, exam_id: int, member_id: int, from_step: int
    ) -> ExamResponse:
        """시험을 다음 진행 단계로 넘긴다.

        클라이언트가 인식한 현재 단계(from_step)를 기준으로 검증한 뒤 `from_step + 1`로
        전진시킨다. 서버의 현재 단계가 from_step보다 뒤처져 있으면 충돌로 처리한다.

        Args:
            exam_id: 단계를 전진시킬 시험 ID
            member_id: 요청한 사용자 ID
            from_step: 클라이언트가 인식한 현재 단계

        Returns:
            갱신된 시험 정보

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ExamStepConflictError: 서버의 현재 단계가 from_step보다 뒤인 경우
        """
        exam = self.repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        if exam.step < from_step:
            raise ExamStepConflictError()
        exam = self.repo.update(exam, step=from_step + 1)
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _to_response(self, exam: Exam, student_count: int) -> ExamResponse:
        """시험 엔티티를 응답 스키마로 변환한다.

        저장된 파일 key들을 조회용 URL로 변환하고 학생 수를 포함한다.

        Args:
            exam: 변환할 시험
            student_count: 시험에 등록된 학생 수

        Returns:
            학생 수와 파일 URL이 포함된 시험 정보
        """
        return ExamResponse(
            exam_id=exam.exam_id,
            name=exam.name,
            description=exam.description,
            step=exam.step,
            layout_mode=exam.layout_mode,
            student_count=student_count,
            problem_sheet_url=get_file_url(exam.problem_sheet_file_key),
            model_answer_url=get_file_url(exam.model_answer_file_key),
            created_at=exam.created_at,
            updated_at=exam.updated_at,
        )


def get_exam_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ExamService:
    return ExamService(ExamRepository(db), StudentRepository(db), storage)
