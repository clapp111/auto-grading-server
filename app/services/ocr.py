from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, OcrResultNotFoundError, StudentNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.ocr_status import OCRStatus
from app.models.ocr_result import OCRResult
from app.repositories.answer_sheet import AnswerSheetRepository
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.ocr_result import OcrResultRepository
from app.repositories.student import StudentRepository
from app.schemas.common import Point, Region
from app.schemas.job import JobStartedResponse
from app.schemas.ocr_result import (
    OcrProgressResponse,
    OcrResultResponse,
    OcrResultUpdateRequest,
    StudentOcrProgressItem,
)


class OcrService:
    def __init__(
        self,
        ocr_result_repo: OcrResultRepository,
        answer_sheet_repo: AnswerSheetRepository,
        exam_repo: ExamRepository,
        student_repo: StudentRepository,
        job_repo: JobRepository,
    ):
        self.ocr_result_repo = ocr_result_repo
        self.answer_sheet_repo = answer_sheet_repo
        self.exam_repo = exam_repo
        self.student_repo = student_repo
        self.job_repo = job_repo

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return exam

    def _get_ocr_result_or_raise(self, ocr_result_id: int, member_id: int) -> OCRResult:
        ocr_result = self.ocr_result_repo.get_by_id(ocr_result_id)
        if not ocr_result:
            raise OcrResultNotFoundError()
        sheet = ocr_result.answer_region.answer_sheet
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        if not exam or exam.member_id != member_id:
            raise OcrResultNotFoundError()
        return ocr_result

    def run_ocr(self, exam_id: int, member_id: int) -> JobStartedResponse:
        from app.workers.ocr_tasks import run_answer_ocr

        self._get_exam_or_raise(exam_id, member_id)
        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_OCR_RUN,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id},
                "source": {"trigger": "api", "endpoint": f"/api/v1/exams/{exam_id}/ocr/run"},
            },
        )
        run_answer_ocr.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def get_progress(self, exam_id: int, member_id: int, search: str | None) -> OcrProgressResponse:
        exam = self._get_exam_or_raise(exam_id, member_id)

        sheets = self.answer_sheet_repo.list_by_exam(exam_id)
        matched_sheets = [s for s in sheets if s.student_id is not None]

        all_items: list[StudentOcrProgressItem] = []
        confirmed_student_count = 0

        for sheet in matched_sheets:
            student = sheet.student
            total, confirmed = self.ocr_result_repo.count_by_answer_sheet(sheet.answer_sheet_id)
            percent = (confirmed * 100 // total) if total > 0 else 0

            if total > 0 and confirmed == total:
                confirmed_student_count += 1

            all_items.append(StudentOcrProgressItem(
                student_id=student.student_id,
                name=student.name,
                student_no=student.student_no,
                confirmed_count=confirmed,
                total_count=total,
                percent=percent,
            ))

        if search:
            all_items = [
                item for item in all_items
                if search in item.name or search in item.student_no
            ]

        return OcrProgressResponse(
            confirmed_student_count=confirmed_student_count,
            total_student_count=exam.student_count,
            students=all_items,
        )

    def list_ocr_results(self, student_id: int, member_id: int) -> list[OcrResultResponse]:
        student = self.student_repo.get_by_id(student_id)
        if not student:
            raise StudentNotFoundError()
        exam = self.exam_repo.get_by_id(student.exam_id)
        if not exam or exam.member_id != member_id:
            raise StudentNotFoundError()

        results = self.ocr_result_repo.list_by_student(student_id)
        return [_to_response(r) for r in results]

    def update_ocr_result(self, ocr_result_id: int, member_id: int, request: OcrResultUpdateRequest) -> OcrResultResponse:
        ocr_result = self._get_ocr_result_or_raise(ocr_result_id, member_id)

        updates = request.model_dump(exclude_unset=True)
        self.ocr_result_repo.update(ocr_result, **updates)

        ocr_result = self.ocr_result_repo.get_by_id(ocr_result_id)
        return _to_response(ocr_result)

    def confirm_ocr_result(self, ocr_result_id: int, member_id: int) -> OcrResultResponse:
        ocr_result = self._get_ocr_result_or_raise(ocr_result_id, member_id)
        self.ocr_result_repo.update(ocr_result, status=OCRStatus.REVIEWED)

        ocr_result = self.ocr_result_repo.get_by_id(ocr_result_id)
        return _to_response(ocr_result)


def _to_response(ocr_result: OCRResult) -> OcrResultResponse:
    region = ocr_result.answer_region
    problem = region.problem
    return OcrResultResponse(
        ocr_result_id=ocr_result.ocr_result_id,
        problem_id=problem.problem_id,
        problem_label=problem.label,
        problem_type=problem.type,
        problem_language=problem.language,
        text=ocr_result.text,
        marked_choice=ocr_result.marked_choice,
        status=ocr_result.status,
        answer_sheet_id=region.answer_sheet_id,
        shape=region.shape,
        bbox_region=Region(**region.bbox_region) if region.bbox_region else None,
        polygon_points=[Point(**p) for p in region.polygon_points] if region.polygon_points else None,
    )


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return OcrService(
        OcrResultRepository(db),
        AnswerSheetRepository(db),
        ExamRepository(db),
        StudentRepository(db),
        JobRepository(db),
    )
