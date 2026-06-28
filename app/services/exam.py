from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError
from app.db.session import get_db
from app.enums.exam_status import ExamStatus
from app.infrastructure.storage.url import get_file_url
from app.models.exam import Exam
from app.repositories.exam import ExamRepository
from app.repositories.student import StudentRepository
from app.schemas.exam import ExamCreateRequest, ExamCursorMeta, ExamResponse, ExamUpdateRequest


class ExamService:
    def __init__(self, repo: ExamRepository, student_repo: StudentRepository):
        self.repo = repo
        self.student_repo = student_repo

    def _to_response(self, exam: Exam) -> ExamResponse:
        return ExamResponse(
            exam_id=exam.exam_id,
            name=exam.name,
            description=exam.description,
            status=exam.status,
            layout_mode=exam.layout_mode,
            student_count=self.student_repo.count_by_exam(exam.exam_id),
            problem_sheet_url=get_file_url(exam.problem_sheet_file_key),
            model_answer_url=get_file_url(exam.model_answer_file_key),
            created_at=exam.created_at,
            updated_at=exam.updated_at,
        )

    def list_exams(
        self,
        member_id: int,
        cursor: str | None,
        size: int,
        search: str | None,
        status: ExamStatus | None,
    ) -> tuple[list[ExamResponse], ExamCursorMeta]:
        cursor_id = int(cursor) if cursor else None
        rows = self.repo.list_by_member(member_id, cursor_id, size, search, status)

        has_more = len(rows) > size
        items = rows[:size]
        next_cursor = str(items[-1].exam_id) if has_more else None

        counts = self.repo.count_by_status(member_id)
        meta = ExamCursorMeta(
            next_cursor=next_cursor,
            has_more=has_more,
            draft=counts["draft"],
            in_progress=counts["in_progress"],
            done=counts["done"],
        )
        return [self._to_response(e) for e in items], meta

    def create_exam(self, member_id: int, request: ExamCreateRequest) -> ExamResponse:
        exam = self.repo.create(
            member_id=member_id,
            name=request.name,
            description=request.description,
        )
        return self._to_response(exam)

    def get_exam(self, exam_id: int, member_id: int) -> ExamResponse:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return self._to_response(exam)

    def update_exam(self, exam_id: int, member_id: int, request: ExamUpdateRequest) -> ExamResponse:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        updates = request.model_dump(exclude_unset=True)
        exam = self.repo.update(exam, **updates)
        return self._to_response(exam)

    def delete_exam(self, exam_id: int, member_id: int) -> None:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        self.repo.delete(exam)


def get_exam_service(db: Session = Depends(get_db)) -> ExamService:
    return ExamService(ExamRepository(db), StudentRepository(db))
