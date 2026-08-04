from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ExamNotFoundError,
    ExamOwnerRequiredError,
    ExamStepConflictError,
    MemberNotFoundError,
)
from app.db.session import get_db
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.infrastructure.storage.url import get_file_url
from app.models.exam import Exam
from app.repositories.exam import ExamRepository
from app.repositories.exam_member import ExamMemberRepository
from app.repositories.member import MemberRepository
from app.repositories.student import StudentRepository
from app.schemas.exam import (
    ExamCreateRequest,
    ExamCursorMeta,
    ExamMemberResponse,
    ExamResponse,
    ExamUpdateRequest,
)


class ExamService:
    def __init__(
        self,
        repo: ExamRepository,
        student_repo: StudentRepository,
        exam_member_repo: ExamMemberRepository,
        member_repo: MemberRepository,
        storage: StorageClient,
    ):
        self.repo = repo
        self.student_repo = student_repo
        self.exam_member_repo = exam_member_repo
        self.member_repo = member_repo
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
            self._to_response(e, student_count_map.get(e.exam_id, 0), member_id)
            for e in items
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
        return self._to_response(
            exam, self.student_repo.count_by_exam(exam.exam_id), member_id
        )

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
        return self._to_response(
            exam, self.student_repo.count_by_exam(exam.exam_id), member_id
        )

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
        return self._to_response(
            exam, self.student_repo.count_by_exam(exam.exam_id), member_id
        )

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
        전진시킨다. 서버의 현재 단계가 from_step과 일치하지 않으면 충돌로 처리한다.

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
        if exam.step != from_step:
            raise ExamStepConflictError()
        exam = self.repo.update(exam, step=from_step + 1)
        return self._to_response(
            exam, self.student_repo.count_by_exam(exam.exam_id), member_id
        )

    def list_exam_members(
        self, exam_id: int, member_id: int
    ) -> list[ExamMemberResponse]:
        """시험의 참여자 목록을 소유자를 포함해 조회한다.

        소유자를 목록 맨 앞에 두고, 초대를 수락한 참여자를 이어서 반환한다.

        Args:
            exam_id: 참여자를 조회할 시험 ID
            member_id: 조회를 요청한 사용자 ID

        Returns:
            소유자와 참여자를 포함한 시험 구성원 목록

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()

        owner = self.member_repo.find_by_id(exam.member_id)
        items = [
            ExamMemberResponse(
                member_id=owner.member_id,
                name=owner.name,
                email=owner.email,
                is_owner=True,
                joined_at=exam.created_at,
            )
        ]
        for exam_member, member in self.exam_member_repo.list_with_member_by_exam(
            exam_id
        ):
            items.append(
                ExamMemberResponse(
                    member_id=member.member_id,
                    name=member.name,
                    email=member.email,
                    is_owner=False,
                    joined_at=exam_member.created_at,
                )
            )
        return items

    def remove_exam_member(
        self, exam_id: int, target_member_id: int, member_id: int
    ) -> None:
        """시험 참여자를 내보내거나 참여자가 스스로 나간다.

        소유자는 임의의 참여자를 내보낼 수 있고, 참여자는 자신만 나갈 수 있다.
        소유자 자신은 대상이 될 수 없다.

        Args:
            exam_id: 대상 시험 ID
            target_member_id: 내보낼(또는 나갈) 참여자 ID
            member_id: 요청한 사용자 ID

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ExamOwnerRequiredError: 남을 내보낼 권한이 없거나 소유자를 대상으로 지정한 경우
            MemberNotFoundError: 대상이 시험 참여자가 아닌 경우
        """
        exam = self.repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        # 소유자는 참여자를 내보낼 수 있고, 참여자는 스스로 나갈 수 있다.
        if exam.member_id != member_id and target_member_id != member_id:
            raise ExamOwnerRequiredError()
        if target_member_id == exam.member_id:
            raise ExamOwnerRequiredError()
        if not self.exam_member_repo.exists(exam_id, target_member_id):
            raise MemberNotFoundError()
        self.exam_member_repo.delete(exam_id, target_member_id)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _to_response(
        self, exam: Exam, student_count: int, member_id: int
    ) -> ExamResponse:
        """시험 엔티티를 응답 스키마로 변환한다.

        저장된 파일 key들을 조회용 URL로 변환하고 학생 수를 포함한다.

        Args:
            exam: 변환할 시험
            student_count: 시험에 등록된 학생 수
            member_id: 현재 요청한 사용자 ID

        Returns:
            학생 수와 파일 URL이 포함된 시험 정보
        """
        return ExamResponse(
            exam_id=exam.exam_id,
            is_owner=exam.member_id == member_id,
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
    return ExamService(
        ExamRepository(db),
        StudentRepository(db),
        ExamMemberRepository(db),
        MemberRepository(db),
        storage,
    )
