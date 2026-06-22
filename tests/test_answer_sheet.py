"""
3단계 학생 식별 영역 지정 서비스 단위 테스트.
DB / Celery 없이 Mock으로 서비스 레이어를 검증합니다.

실행: pytest tests/test_answer_sheet_id_region.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pytest
from unittest.mock import MagicMock, patch

from app.enums.job_status import JobStatus
from app.enums.job_type import JobType
from app.enums.sheet_status import SheetStatus
from app.schemas.answer_sheet import IdRegionSaveRequest, AnswerSheetPatchRequest
from app.schemas.common import Region
from app.schemas.s3 import PresignedUrlRequest
from app.services.answer_sheet import AnswerSheetService


# ── Mock 데이터 ─────────────────────────────────────────────────

MEMBER_ID = 10
EXAM_ID = 1
ANSWER_SHEET_ID = 101
JOB_ID = 999

NAME_REGION = Region(page=1, x=100, y=50, w=200, h=30)
STUDENT_NO_REGION = Region(page=1, x=100, y=90, w=200, h=30)

FILE_KEY = f"exams/{EXAM_ID}/answer-sheets/abc123def456.pdf"
CDN_URL = f"https://cdn.example.com/{FILE_KEY}"
UPLOAD_URL = "https://s3.amazonaws.com/bucket/presigned-put?X-Amz-Signature=stub"


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def mock_exam():
    exam = MagicMock()
    exam.exam_id = EXAM_ID
    exam.member_id = MEMBER_ID
    exam.student_name_region = None
    exam.student_no_region = None
    return exam


@pytest.fixture
def mock_sheet():
    sheet = MagicMock()
    sheet.answer_sheet_id = ANSWER_SHEET_ID
    sheet.exam_id = EXAM_ID
    sheet.file_key = FILE_KEY
    sheet.status = SheetStatus.UNMATCHED
    sheet.student_id = None
    sheet.student = None
    return sheet


@pytest.fixture
def mock_job():
    job = MagicMock()
    job.job_id = JOB_ID
    job.status = JobStatus.PENDING
    return job


@pytest.fixture
def service_with_mocks(mock_exam, mock_sheet, mock_job):
    answer_sheet_repo = MagicMock()
    student_repo = MagicMock()
    exam_repo = MagicMock()
    job_repo = MagicMock()
    storage = MagicMock()

    exam_repo.get_by_id.return_value = mock_exam
    answer_sheet_repo.get_by_id.return_value = mock_sheet
    answer_sheet_repo.list_by_exam.return_value = [mock_sheet]
    answer_sheet_repo.create.return_value = mock_sheet
    job_repo.create.return_value = mock_job
    storage.generate_key.return_value = FILE_KEY
    storage.generate_presigned_url.return_value = UPLOAD_URL

    svc = AnswerSheetService(
        answer_sheet_repo=answer_sheet_repo,
        student_repo=student_repo,
        exam_repo=exam_repo,
        job_repo=job_repo,
        storage=storage,
    )
    mocks = {
        "answer_sheet_repo": answer_sheet_repo,
        "student_repo": student_repo,
        "exam_repo": exam_repo,
        "job_repo": job_repo,
        "storage": storage,
    }
    return svc, mocks


# ── 1. 답안지 업로드 URL 발급 ──────────────────────────────────────

class TestIssueUploadUrl:
    def test_creates_answer_sheet_record(self, service_with_mocks):
        svc, mocks = service_with_mocks
        req = PresignedUrlRequest(file_name="홍길동_답안지.pdf", content_type="application/pdf")

        svc.issue_upload_url(EXAM_ID, MEMBER_ID, req)

        mocks["answer_sheet_repo"].create.assert_called_once_with(
            exam_id=EXAM_ID, file_key=FILE_KEY
        )

    def test_returns_presigned_url_and_file_key(self, service_with_mocks):
        svc, mocks = service_with_mocks
        req = PresignedUrlRequest(file_name="홍길동_답안지.pdf", content_type="application/pdf")

        result = svc.issue_upload_url(EXAM_ID, MEMBER_ID, req)

        assert result.upload_url == UPLOAD_URL
        assert result.file_key == FILE_KEY


# ── 2. 식별 영역 저장 및 OCR 작업 시작 ──────────────────────────────

class TestSaveIdRegions:
    @pytest.fixture
    def id_region_req(self):
        return IdRegionSaveRequest(
            name_region=NAME_REGION,
            student_no_region=STUDENT_NO_REGION,
        )

    def test_saves_regions_to_exam(self, service_with_mocks, id_region_req, mock_exam):
        svc, mocks = service_with_mocks

        with patch("app.workers.ocr_tasks.run_student_id_ocr") as mock_task:
            mock_task.delay.return_value = None
            svc.save_id_regions(EXAM_ID, MEMBER_ID, id_region_req)

        mocks["exam_repo"].update.assert_called_once_with(
            mock_exam,
            student_name_region=NAME_REGION.model_dump(),
            student_no_region=STUDENT_NO_REGION.model_dump(),
        )

    def test_creates_job_with_answer_sheet_recognize_type(self, service_with_mocks, id_region_req):
        svc, mocks = service_with_mocks

        with patch("app.workers.ocr_tasks.run_student_id_ocr") as mock_task:
            mock_task.delay.return_value = None
            svc.save_id_regions(EXAM_ID, MEMBER_ID, id_region_req)

        kwargs = mocks["job_repo"].create.call_args.kwargs
        assert kwargs["type"] == JobType.ANSWER_SHEET_RECOGNIZE
        assert kwargs["exam_id"] == EXAM_ID
        assert kwargs["requested_by_member_id"] == MEMBER_ID

    def test_dispatches_celery_task_with_job_id(self, service_with_mocks, id_region_req):
        svc, mocks = service_with_mocks

        with patch("app.workers.ocr_tasks.run_student_id_ocr") as mock_task:
            mock_task.delay.return_value = None
            svc.save_id_regions(EXAM_ID, MEMBER_ID, id_region_req)

        mock_task.delay.assert_called_once_with(JOB_ID)

    def test_returns_job_started_response(self, service_with_mocks, id_region_req):
        svc, mocks = service_with_mocks

        with patch("app.workers.ocr_tasks.run_student_id_ocr") as mock_task:
            mock_task.delay.return_value = None
            result = svc.save_id_regions(EXAM_ID, MEMBER_ID, id_region_req)

        assert result.job_id == JOB_ID
        assert result.status == JobStatus.PENDING


# ── 3. 답안지 목록 조회 ──────────────────────────────────────────────

class TestListAnswerSheets:
    def test_returns_unmatched_sheets(self, service_with_mocks):
        svc, _ = service_with_mocks

        result = svc.list_answer_sheets(EXAM_ID, MEMBER_ID)

        assert len(result) == 1
        assert result[0].answer_sheet_id == ANSWER_SHEET_ID
        assert result[0].status == SheetStatus.UNMATCHED
        assert result[0].student_id is None
        assert result[0].student_name is None


# ── 4. 답안지 다운로드 URL 조회 ────────────────────────────────────

class TestGetDownloadUrl:
    def test_returns_cdn_url(self, service_with_mocks):
        svc, _ = service_with_mocks

        with patch("app.services.answer_sheet.get_file_url", return_value=CDN_URL):
            result = svc.get_download_url(ANSWER_SHEET_ID, MEMBER_ID)

        assert result.url == CDN_URL

    def test_includes_exam_regions_when_configured(self, service_with_mocks, mock_exam):
        svc, _ = service_with_mocks
        mock_exam.student_name_region = NAME_REGION.model_dump()
        mock_exam.student_no_region = STUDENT_NO_REGION.model_dump()

        with patch("app.services.answer_sheet.get_file_url", return_value=CDN_URL):
            result = svc.get_download_url(ANSWER_SHEET_ID, MEMBER_ID)

        assert result.student_name_region == NAME_REGION
        assert result.student_no_region == STUDENT_NO_REGION

    def test_regions_are_none_when_not_configured(self, service_with_mocks, mock_exam):
        svc, _ = service_with_mocks
        mock_exam.student_name_region = None
        mock_exam.student_no_region = None

        with patch("app.services.answer_sheet.get_file_url", return_value=CDN_URL):
            result = svc.get_download_url(ANSWER_SHEET_ID, MEMBER_ID)

        assert result.student_name_region is None
        assert result.student_no_region is None


# ── 5. 답안지 수동 매칭 (PATCH) ──────────────────────────────────────

class TestPatchAnswerSheet:
    def test_creates_new_student_when_not_found(self, service_with_mocks, mock_sheet):
        svc, mocks = service_with_mocks
        mocks["student_repo"].get_by_exam_and_no.return_value = None
        new_student = MagicMock(student_id=50)
        mocks["student_repo"].create.return_value = new_student

        svc.patch_answer_sheet(
            ANSWER_SHEET_ID, MEMBER_ID,
            AnswerSheetPatchRequest(name="홍길동", student_no="20230001"),
        )

        mocks["student_repo"].create.assert_called_once_with(
            exam_id=EXAM_ID, name="홍길동", student_no="20230001"
        )

    def test_updates_name_for_existing_student(self, service_with_mocks):
        svc, mocks = service_with_mocks
        existing = MagicMock(student_id=50)
        mocks["student_repo"].get_by_exam_and_no.return_value = existing

        svc.patch_answer_sheet(
            ANSWER_SHEET_ID, MEMBER_ID,
            AnswerSheetPatchRequest(name="홍길동(수정)", student_no="20230001"),
        )

        mocks["student_repo"].update.assert_called_once_with(existing, name="홍길동(수정)")
        mocks["student_repo"].create.assert_not_called()

    def test_sets_sheet_status_to_matched(self, service_with_mocks, mock_sheet):
        svc, mocks = service_with_mocks
        mocks["student_repo"].get_by_exam_and_no.return_value = None
        student = MagicMock(student_id=50)
        mocks["student_repo"].create.return_value = student

        svc.patch_answer_sheet(
            ANSWER_SHEET_ID, MEMBER_ID,
            AnswerSheetPatchRequest(name="홍길동", student_no="20230001"),
        )

        mocks["answer_sheet_repo"].update.assert_called_once_with(
            mock_sheet,
            student_id=student.student_id,
            status=SheetStatus.MATCHED,
        )
