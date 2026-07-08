from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AnswerSheetNotFoundError, ExamNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.sheet_status import SheetStatus
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.infrastructure.storage.url import get_file_url
from app.models.answer_sheet import AnswerSheet
from app.repositories.answer_sheet import AnswerSheetRepository
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.student import StudentRepository
from app.schemas.answer_sheet import (
    AnswerSheetDownloadResponse,
    AnswerSheetPatchRequest,
    AnswerSheetPresignedUrlResponse,
    AnswerSheetResponse,
    IdRegionSaveRequest,
    UploadCompleteResponse,
)
from app.schemas.job import JobStartedResponse
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class AnswerSheetService:
    def __init__(
        self,
        db: Session,
        answer_sheet_repo: AnswerSheetRepository,
        student_repo: StudentRepository,
        exam_repo: ExamRepository,
        job_repo: JobRepository,
        storage: StorageClient,
    ):
        self.db = db
        self.answer_sheet_repo = answer_sheet_repo
        self.student_repo = student_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo
        self.storage = storage

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return exam

    def _get_sheet_or_raise(self, answer_sheet_id: int, member_id: int) -> AnswerSheet:
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        if not exam or exam.member_id != member_id:
            raise AnswerSheetNotFoundError()
        return sheet

    def issue_upload_url(self, exam_id: int, member_id: int, request: PresignedUrlRequest) -> AnswerSheetPresignedUrlResponse:
        self._get_exam_or_raise(exam_id, member_id)
        file_key = self.storage.generate_key(f"exams/{exam_id}/answer-sheets", request.file_name)
        sheet = self.answer_sheet_repo.create(exam_id=exam_id, file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        self.exam_repo.touch(exam_id)
        return AnswerSheetPresignedUrlResponse(upload_url=upload_url, file_key=file_key, answer_sheet_id=sheet.answer_sheet_id)

    def list_answer_sheets(self, exam_id: int, member_id: int) -> list[AnswerSheetResponse]:
        self._get_exam_or_raise(exam_id, member_id)
        sheets = self.answer_sheet_repo.list_by_exam(exam_id)
        student_ids = [s.student_id for s in sheets if s.student_id]
        student_map = self.student_repo.map_by_ids(student_ids)
        sheets.sort(key=lambda x: student_map[x.student_id].student_no if x.student_id and x.student_id in student_map else "")
        return [
            _to_response(
                s,
                student_map[s.student_id].name if s.student_id and s.student_id in student_map else None,
                student_map[s.student_id].student_no if s.student_id and s.student_id in student_map else None,
            )
            for s in sheets
        ]

    def delete_answer_sheet(self, answer_sheet_id: int, member_id: int) -> None:
        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        student = self.student_repo.get_by_id(sheet.student_id) if sheet.student_id else None

        self.answer_sheet_repo.delete(sheet, commit=False)
        if student:
            self.student_repo.delete(student, commit=False)

        self.db.commit()
        self.storage.delete(sheet.file_key)
        self.exam_repo.touch(exam_id)

    def get_download_url(self, answer_sheet_id: int, member_id: int) -> AnswerSheetDownloadResponse:
        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        return AnswerSheetDownloadResponse(
            url=get_file_url(sheet.file_key),
            student_name_region=exam.student_name_region,
            student_no_region=exam.student_no_region,
        )

    def save_id_regions(self, exam_id: int, member_id: int, request: IdRegionSaveRequest) -> JobStartedResponse:
        from app.workers.ocr_tasks import run_student_id_ocr

        exam = self._get_exam_or_raise(exam_id, member_id)
        self.exam_repo.update(
            exam,
            student_name_region=request.name_region.model_dump(),
            student_no_region=request.student_no_region.model_dump(),
        )
        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_SHEET_RECOGNIZE,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id},
                "source": {"trigger": "api", "endpoint": f"/api/v1/exams/{exam_id}/id-regions"},
            },
        )
        run_student_id_ocr.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def complete_upload(self, answer_sheet_id: int, member_id: int) -> UploadCompleteResponse:
        from app.workers.ocr_tasks import run_student_id_ocr

        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        exam = self.exam_repo.get_by_id(exam_id)

        if sheet.status != SheetStatus.UNMATCHED or not (exam.student_name_region and exam.student_no_region):
            return UploadCompleteResponse(answer_sheet_id=answer_sheet_id)

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_SHEET_RECOGNIZE,
            requested_by_member_id=member_id,
            input_json={
                "answer_sheet_ids": [answer_sheet_id],
                "source": {"trigger": "upload_complete", "answerSheetId": answer_sheet_id},
            },
        )
        run_student_id_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return UploadCompleteResponse(answer_sheet_id=answer_sheet_id, job_id=job.job_id)

    def run_answer_sheet_ocr(self, answer_sheet_id: int, member_id: int) -> JobStartedResponse:
        from app.workers.ocr_tasks import run_answer_ocr

        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_OCR_RUN,
            requested_by_member_id=member_id,
            answer_sheet_id=answer_sheet_id,
            input_json={
                "source": {"trigger": "api", "endpoint": f"/api/v1/answer-sheets/{answer_sheet_id}/ocr"},
            },
        )
        run_answer_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def patch_answer_sheet(self, answer_sheet_id: int, member_id: int, request: AnswerSheetPatchRequest) -> AnswerSheetResponse:
        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)

        if request.student_no:
            exam_id = sheet.exam_id
            student = self.student_repo.get_by_exam_and_no(exam_id, request.student_no)
            if student:
                if request.name:
                    self.student_repo.update(student, name=request.name)
            else:
                student = self.student_repo.create(
                    exam_id=exam_id,
                    name=request.name or "",
                    student_no=request.student_no,
                )
            self.answer_sheet_repo.update(sheet, student_id=student.student_id, status=SheetStatus.MATCHED)
            self.exam_repo.touch(exam_id)

        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        student = self.student_repo.get_by_id(sheet.student_id) if sheet.student_id else None
        return _to_response(sheet, student.name if student else None, student.student_no if student else None)


def _to_response(sheet: AnswerSheet, student_name: str | None, student_no: str | None) -> AnswerSheetResponse:
    return AnswerSheetResponse(
        answer_sheet_id=sheet.answer_sheet_id,
        exam_id=sheet.exam_id,
        file_key=sheet.file_key,
        status=sheet.status,
        student_id=sheet.student_id,
        student_name=student_name,
        student_no=student_no,
    )


def get_answer_sheet_service(
    db: Session = Depends(get_db),
    storage: StorageClient = Depends(get_storage),
) -> AnswerSheetService:
    return AnswerSheetService(
        db,
        AnswerSheetRepository(db),
        StudentRepository(db),
        ExamRepository(db),
        JobRepository(db),
        storage,
    )
