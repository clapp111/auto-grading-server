import os
import sys
from unittest.mock import MagicMock

from dotenv import load_dotenv
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.core.exceptions import AnswerRegionNotFoundError, OcrResultNotFoundError
from app.enums.layout_mode import LayoutMode
from app.enums.ocr_status import OCRStatus
from app.enums.problem_type import ProblemType
from app.enums.region_shape import RegionShape
from app.schemas.answer_region import AnswerRegionCreateRequest, AnswerRegionUpdateRequest
from app.schemas.common import Region
from app.services.ocr import OcrService
from app.services.region import RegionService


MEMBER_ID = 10
EXAM_ID = 1
ANSWER_SHEET_ID = 101
ANSWER_REGION_ID = 201
STUDENT_ID = 301
OCR_RESULT_ID = 401


def _make_exam(layout_mode: LayoutMode = LayoutMode.FREE):
    exam = MagicMock()
    exam.exam_id = EXAM_ID
    exam.member_id = MEMBER_ID
    exam.layout_mode = layout_mode
    exam.student_count = 1
    return exam


def _make_sheet():
    sheet = MagicMock()
    sheet.answer_sheet_id = ANSWER_SHEET_ID
    sheet.exam_id = EXAM_ID
    sheet.student_id = STUDENT_ID
    sheet.student = MagicMock(student_id=STUDENT_ID, name="테스트 학생", student_no="20220002")
    return sheet


def _make_region(layout_mode: LayoutMode = LayoutMode.FREE, problem_id: int = 1):
    region = MagicMock()
    region.answer_region_id = ANSWER_REGION_ID
    region.answer_sheet_id = ANSWER_SHEET_ID
    region.problem_id = problem_id
    region.layout_mode = layout_mode
    region.shape = RegionShape.RECT
    region.bbox_region = {"page": 1, "x": 10, "y": 20, "w": 100, "h": 50}
    region.polygon_points = None
    region.problem = MagicMock(label=f"Q{problem_id}")
    return region


def _make_ocr_result(layout_mode: LayoutMode = LayoutMode.FREE):
    region = _make_region(layout_mode=layout_mode)
    region.answer_sheet = _make_sheet()
    region.problem.type = ProblemType.DESCRIPTIVE
    region.problem.language = None

    result = MagicMock()
    result.ocr_result_id = OCR_RESULT_ID
    result.answer_region = region
    result.text = "answer"
    result.marked_choice = None
    result.status = OCRStatus.RAW
    return result


class TestRegionServiceModeFiltering:
    def test_list_regions_uses_active_exam_layout_mode(self):
        answer_region_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        job_repo = MagicMock()

        sheet = _make_sheet()
        exam = _make_exam(LayoutMode.FREE)
        region = _make_region(LayoutMode.FREE)

        answer_sheet_repo.get_by_id.return_value = sheet
        exam_repo.get_by_id.return_value = exam
        answer_region_repo.list_by_answer_sheet.return_value = [region]

        service = RegionService(answer_region_repo, answer_sheet_repo, exam_repo, job_repo)
        result = service.list_regions(ANSWER_SHEET_ID, MEMBER_ID)

        answer_region_repo.list_by_answer_sheet.assert_called_once_with(ANSWER_SHEET_ID, LayoutMode.FREE)
        assert len(result) == 1
        assert result[0].layout_mode == LayoutMode.FREE

    def test_create_region_upserts_within_active_layout_mode(self):
        answer_region_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        job_repo = MagicMock()

        sheet = _make_sheet()
        exam = _make_exam(LayoutMode.FREE)
        region = _make_region(LayoutMode.FREE)
        request = AnswerRegionCreateRequest(
            problem_id=1,
            shape=RegionShape.RECT,
            bbox_region=Region(page=1, x=1, y=2, w=3, h=4),
        )

        answer_sheet_repo.get_by_id.return_value = sheet
        exam_repo.get_by_id.return_value = exam
        answer_region_repo.get_by_sheet_problem_and_mode.return_value = region
        answer_region_repo.get_by_id.return_value = region

        service = RegionService(answer_region_repo, answer_sheet_repo, exam_repo, job_repo)
        service.create_region(ANSWER_SHEET_ID, MEMBER_ID, request)

        answer_region_repo.get_by_sheet_problem_and_mode.assert_called_once_with(
            answer_sheet_id=ANSWER_SHEET_ID,
            problem_id=1,
            layout_mode=LayoutMode.FREE,
        )
        answer_region_repo.update.assert_called_once()
        answer_region_repo.create.assert_not_called()

    def test_update_region_rejects_inactive_layout_mode(self):
        answer_region_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        job_repo = MagicMock()

        region = _make_region(LayoutMode.FIXED)
        sheet = _make_sheet()
        exam = _make_exam(LayoutMode.FREE)

        answer_region_repo.get_by_id.return_value = region
        answer_sheet_repo.get_by_id.return_value = sheet
        exam_repo.get_by_id.return_value = exam

        service = RegionService(answer_region_repo, answer_sheet_repo, exam_repo, job_repo)

        with pytest.raises(AnswerRegionNotFoundError):
            service.update_region(ANSWER_REGION_ID, MEMBER_ID, AnswerRegionUpdateRequest(problem_id=2))


class TestOcrServiceModeFiltering:
    def test_get_progress_counts_only_active_layout_mode(self):
        ocr_result_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        student_repo = MagicMock()
        job_repo = MagicMock()

        exam = _make_exam(LayoutMode.FIXED)
        sheet = _make_sheet()

        exam_repo.get_by_id.return_value = exam
        answer_sheet_repo.list_by_exam.return_value = [sheet]
        ocr_result_repo.count_by_answer_sheet.return_value = (3, 2)

        service = OcrService(ocr_result_repo, answer_sheet_repo, exam_repo, student_repo, job_repo)
        result = service.get_progress(EXAM_ID, MEMBER_ID, None)

        ocr_result_repo.count_by_answer_sheet.assert_called_once_with(ANSWER_SHEET_ID, LayoutMode.FIXED)
        assert result.students[0].total_count == 3
        assert result.students[0].confirmed_count == 2

    def test_get_progress_uses_current_matched_sheet_count_instead_of_exam_student_count(self):
        ocr_result_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        student_repo = MagicMock()
        job_repo = MagicMock()

        exam = _make_exam(LayoutMode.FIXED)
        exam.student_count = 5
        sheet = _make_sheet()

        exam_repo.get_by_id.return_value = exam
        answer_sheet_repo.list_by_exam.return_value = [sheet]
        ocr_result_repo.count_by_answer_sheet.return_value = (3, 3)

        service = OcrService(ocr_result_repo, answer_sheet_repo, exam_repo, student_repo, job_repo)
        result = service.get_progress(EXAM_ID, MEMBER_ID, None)

        assert result.total_student_count == 1

    def test_list_results_filters_by_active_layout_mode(self):
        ocr_result_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        student_repo = MagicMock()
        job_repo = MagicMock()

        student = MagicMock()
        student.student_id = STUDENT_ID
        student.exam_id = EXAM_ID

        exam = _make_exam(LayoutMode.FREE)
        result_row = _make_ocr_result(LayoutMode.FREE)

        student_repo.get_by_id.return_value = student
        exam_repo.get_by_id.return_value = exam
        ocr_result_repo.list_by_student.return_value = [result_row]

        service = OcrService(ocr_result_repo, answer_sheet_repo, exam_repo, student_repo, job_repo)
        result = service.list_ocr_results(STUDENT_ID, MEMBER_ID)

        ocr_result_repo.list_by_student.assert_called_once_with(STUDENT_ID, LayoutMode.FREE)
        assert len(result) == 1
        assert result[0].answer_sheet_id == ANSWER_SHEET_ID

    def test_update_result_rejects_inactive_layout_mode(self):
        ocr_result_repo = MagicMock()
        answer_sheet_repo = MagicMock()
        exam_repo = MagicMock()
        student_repo = MagicMock()
        job_repo = MagicMock()

        result_row = _make_ocr_result(LayoutMode.FIXED)
        exam = _make_exam(LayoutMode.FREE)

        ocr_result_repo.get_by_id.return_value = result_row
        exam_repo.get_by_id.return_value = exam

        service = OcrService(ocr_result_repo, answer_sheet_repo, exam_repo, student_repo, job_repo)

        with pytest.raises(OcrResultNotFoundError):
            service.confirm_ocr_result(OCR_RESULT_ID, MEMBER_ID)
