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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def issue_upload_url(
        self, exam_id: int, member_id: int, request: PresignedUrlRequest
    ) -> AnswerSheetPresignedUrlResponse:
        """답안지 업로드용 presigned URL을 발급하고 답안지 레코드를 생성한다.

        업로드 전에 file key로 답안지 레코드를 먼저 만든다.

        Args:
            exam_id: 답안지를 올릴 시험 ID
            member_id: 요청한 사용자 ID
            request: 파일명과 content type

        Returns:
            업로드 URL, file key, 생성된 답안지 ID

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        self._get_exam_or_raise(exam_id, member_id)
        file_key = self.storage.generate_key(
            f"exams/{exam_id}/answer-sheets", request.file_name
        )
        sheet = self.answer_sheet_repo.create(exam_id=exam_id, file_key=file_key)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        self.exam_repo.touch(exam_id)
        return AnswerSheetPresignedUrlResponse(
            upload_url=upload_url,
            file_key=file_key,
            answer_sheet_id=sheet.answer_sheet_id,
        )

    def list_answer_sheets(
        self, exam_id: int, member_id: int
    ) -> list[AnswerSheetResponse]:
        """시험의 답안지 목록을 학번 순으로 조회한다.

        매칭된 학생의 이름·학번을 함께 담고, 학번 오름차순으로 정렬한다.

        Args:
            exam_id: 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            학생 정보가 포함된 답안지 목록

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        self._get_exam_or_raise(exam_id, member_id)
        sheets = self.answer_sheet_repo.list_by_exam(exam_id)
        student_ids = [s.student_id for s in sheets if s.student_id]
        student_map = self.student_repo.map_by_ids(student_ids)
        sheets.sort(
            key=lambda x: (
                student_map[x.student_id].student_no
                if x.student_id and x.student_id in student_map
                else ""
            )
        )
        return [
            _to_response(
                s,
                (
                    student_map[s.student_id].name
                    if s.student_id and s.student_id in student_map
                    else None
                ),
                (
                    student_map[s.student_id].student_no
                    if s.student_id and s.student_id in student_map
                    else None
                ),
            )
            for s in sheets
        ]

    def delete_answer_sheet(self, answer_sheet_id: int, member_id: int) -> None:
        """답안지를 삭제한다.

        매칭된 학생이 있으면 함께 삭제하고, DB 커밋 후 S3 파일을 제거한다.

        Args:
            answer_sheet_id: 삭제할 답안지 ID
            member_id: 요청한 사용자 ID

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        student = (
            self.student_repo.get_by_id(sheet.student_id) if sheet.student_id else None
        )

        self.answer_sheet_repo.delete(sheet, commit=False)
        if student:
            self.student_repo.delete(student, commit=False)

        self.db.commit()
        self.storage.delete(sheet.file_key)
        self.exam_repo.touch(exam_id)

    def get_download_url(
        self, answer_sheet_id: int, member_id: int
    ) -> AnswerSheetDownloadResponse:
        """답안지 다운로드 URL과 학번·이름 영역 정보를 조회한다.

        Args:
            answer_sheet_id: 대상 답안지 ID
            member_id: 요청한 사용자 ID

        Returns:
            다운로드 URL과 학생 이름·학번 영역 좌표

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        return AnswerSheetDownloadResponse(
            url=get_file_url(sheet.file_key),
            student_name_region=exam.student_name_region,
            student_no_region=exam.student_no_region,
        )

    def save_id_regions(
        self, exam_id: int, member_id: int, request: IdRegionSaveRequest
    ) -> JobStartedResponse:
        """학생 이름·학번 영역을 저장하고 답안지 인식 잡을 실행한다.

        영역을 시험에 저장한 뒤, 전체 답안지의 학생 정보를 OCR로 인식하는 잡을 시작한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID
            request: 이름 영역과 학번 영역 좌표

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
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
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/exams/{exam_id}/id-regions",
                },
            },
        )
        run_student_id_ocr.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def complete_upload(
        self, answer_sheet_id: int, member_id: int
    ) -> UploadCompleteResponse:
        """답안지 업로드 완료를 처리하고 필요 시 학생 인식 잡을 실행한다.

        답안지가 아직 미매칭이고 이름·학번 영역이 설정돼 있을 때만 인식 잡을 시작한다.
        그 외에는 잡 없이 답안지 ID만 반환한다.

        Args:
            answer_sheet_id: 업로드 완료된 답안지 ID
            member_id: 요청한 사용자 ID

        Returns:
            답안지 ID와 (시작된 경우) 잡 ID

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_student_id_ocr

        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        exam = self.exam_repo.get_by_id(exam_id)

        if sheet.status != SheetStatus.UNMATCHED or not (
            exam.student_name_region and exam.student_no_region
        ):
            return UploadCompleteResponse(answer_sheet_id=answer_sheet_id)

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_SHEET_RECOGNIZE,
            requested_by_member_id=member_id,
            input_json={
                "answer_sheet_ids": [answer_sheet_id],
                "source": {
                    "trigger": "upload_complete",
                    "answerSheetId": answer_sheet_id,
                },
            },
        )
        run_student_id_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return UploadCompleteResponse(
            answer_sheet_id=answer_sheet_id, job_id=job.job_id
        )

    def run_answer_sheet_ocr(
        self, answer_sheet_id: int, member_id: int
    ) -> JobStartedResponse:
        """답안지의 답안 영역 OCR 잡을 생성해 비동기로 실행한다.

        Args:
            answer_sheet_id: 대상 답안지 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_answer_ocr

        sheet = self._get_sheet_or_raise(answer_sheet_id, member_id)
        exam_id = sheet.exam_id
        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_OCR_RUN,
            requested_by_member_id=member_id,
            answer_sheet_id=answer_sheet_id,
            input_json={
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/answer-sheets/{answer_sheet_id}/ocr",
                },
            },
        )
        run_answer_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def patch_answer_sheet(
        self, answer_sheet_id: int, member_id: int, request: AnswerSheetPatchRequest
    ) -> AnswerSheetResponse:
        """답안지에 학생을 수동으로 매칭한다.

        학번이 주어지면 해당 학생을 찾거나 새로 만들어 답안지에 연결하고 상태를 MATCHED로
        바꾼다. 이름만 주어지면 기존 학생의 이름만 갱신한다.

        Args:
            answer_sheet_id: 대상 답안지 ID
            member_id: 요청한 사용자 ID
            request: 매칭할 학생의 학번·이름

        Returns:
            갱신된 답안지 정보

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
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
            self.answer_sheet_repo.update(
                sheet, student_id=student.student_id, status=SheetStatus.MATCHED
            )
            self.exam_repo.touch(exam_id)

        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        student = (
            self.student_repo.get_by_id(sheet.student_id) if sheet.student_id else None
        )
        return _to_response(
            sheet,
            student.name if student else None,
            student.student_no if student else None,
        )

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
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

    def _get_sheet_or_raise(self, answer_sheet_id: int, member_id: int) -> AnswerSheet:
        """답안지를 조회하고, 없거나 접근 권한이 없으면 예외를 던진다.

        Args:
            answer_sheet_id: 조회할 답안지 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 답안지

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_accessible(sheet.exam_id, member_id)
        if not exam:
            raise AnswerSheetNotFoundError()
        return sheet


def _to_response(
    sheet: AnswerSheet, student_name: str | None, student_no: str | None
) -> AnswerSheetResponse:
    """답안지 엔티티를 학생 정보와 합쳐 응답 스키마로 변환한다.

    Args:
        sheet: 변환할 답안지
        student_name: 매칭된 학생 이름 (없으면 `None`)
        student_no: 매칭된 학생 학번 (없으면 `None`)

    Returns:
        학생 정보가 포함된 답안지 응답
    """
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
