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
from app.schemas.exam import ExamCreateRequest, ExamCursorMeta, ExamResponse, ExamUpdateRequest


class ExamService:
    def __init__(self, repo: ExamRepository, student_repo: StudentRepository, storage: StorageClient):
        self.repo = repo
        self.student_repo = student_repo
        self.storage = storage

    def _to_response(self, exam: Exam, student_count: int) -> ExamResponse:
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

    def list_exams(
        self,
        member_id: int,
        cursor: str | None,
        size: int,
        search: str | None,
        step: int | None,
    ) -> tuple[list[ExamResponse], ExamCursorMeta]:
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
        return [self._to_response(e, student_count_map.get(e.exam_id, 0)) for e in items], meta

    def create_exam(self, member_id: int, request: ExamCreateRequest) -> ExamResponse:
        exam = self.repo.create(
            member_id=member_id,
            name=request.name,
            description=request.description,
        )
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def get_exam(self, exam_id: int, member_id: int) -> ExamResponse:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def update_exam(self, exam_id: int, member_id: int, request: ExamUpdateRequest) -> ExamResponse:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        updates = request.model_dump(exclude_unset=True)
        exam = self.repo.update(exam, **updates)
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))

    def delete_exam(self, exam_id: int, member_id: int) -> None:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()

        s3_keys = self.repo.get_answer_sheet_file_keys(exam_id)
        if exam.problem_sheet_file_key:
            s3_keys.append(exam.problem_sheet_file_key)
        if exam.model_answer_file_key:
            s3_keys.append(exam.model_answer_file_key)

        self.repo.delete(exam_id)

        for key in s3_keys:
            self.storage.delete(key)

    def advance_step(self, exam_id: int, member_id: int, from_step: int) -> ExamResponse:
        exam = self.repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        if exam.step < from_step:
            raise ExamStepConflictError()
        exam = self.repo.update(exam, step=from_step + 1)
        return self._to_response(exam, self.student_repo.count_by_exam(exam.exam_id))


def get_exam_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> ExamService:
    return ExamService(ExamRepository(db), StudentRepository(db), storage)
