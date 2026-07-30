from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ExamNotFoundError,
    OcrResultNotFoundError,
    StudentNotFoundError,
)
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.ocr_status import OCRStatus
from app.models.answer_region import AnswerRegion
from app.models.ocr_result import OCRResult
from app.models.problem import Problem
from app.repositories.answer_region import AnswerRegionRepository
from app.repositories.answer_sheet import AnswerSheetRepository
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.ocr_result import OcrResultRepository
from app.repositories.problem import ProblemRepository
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
        answer_region_repo: AnswerRegionRepository,
        answer_sheet_repo: AnswerSheetRepository,
        exam_repo: ExamRepository,
        student_repo: StudentRepository,
        problem_repo: ProblemRepository,
        job_repo: JobRepository,
    ):
        self.ocr_result_repo = ocr_result_repo
        self.answer_region_repo = answer_region_repo
        self.answer_sheet_repo = answer_sheet_repo
        self.exam_repo = exam_repo
        self.student_repo = student_repo
        self.problem_repo = problem_repo
        self.job_repo = job_repo

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def run_ocr(self, exam_id: int, member_id: int) -> JobStartedResponse:
        """시험 전체 답안 영역의 OCR 잡을 생성해 비동기로 실행한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        from app.workers.ocr_tasks import run_answer_ocr

        exam = self._get_exam_or_raise(exam_id, member_id)
        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.ANSWER_OCR_RUN,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id, "layoutMode": exam.layout_mode},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/exams/{exam_id}/ocr/run",
                },
            },
        )
        run_answer_ocr.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def get_progress(
        self, exam_id: int, member_id: int, search: str | None
    ) -> OcrProgressResponse:
        """학생별 OCR 검수 진행 현황을 조회한다.

        학생이 매칭된 답안지만 대상으로, 확정된 영역 비율(percent)과 전체 확정 학생 수를
        집계한다. 검색어가 있으면 이름·학번으로 거른 뒤 학번 순으로 정렬한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID
            search: 이름·학번 검색어

        Returns:
            학생별 진행 항목과 확정/전체 학생 수 요약

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self._get_exam_or_raise(exam_id, member_id)

        sheets = self.answer_sheet_repo.list_by_exam(exam_id)
        matched_sheets = [s for s in sheets if s.student_id is not None]
        student_map = self.student_repo.map_by_ids(
            [s.student_id for s in matched_sheets]
        )

        all_items: list[StudentOcrProgressItem] = []
        confirmed_student_count = 0

        count_map = self.ocr_result_repo.count_by_answer_sheets(
            [s.answer_sheet_id for s in matched_sheets], exam.layout_mode
        )
        for sheet in matched_sheets:
            student = student_map[sheet.student_id]
            total, confirmed = count_map.get(sheet.answer_sheet_id, (0, 0))
            percent = (confirmed * 100 // total) if total > 0 else 0

            if total > 0 and confirmed == total:
                confirmed_student_count += 1

            all_items.append(
                StudentOcrProgressItem(
                    student_id=student.student_id,
                    name=student.name,
                    student_no=student.student_no,
                    confirmed_count=confirmed,
                    total_count=total,
                    percent=percent,
                )
            )

        if search:
            all_items = [
                item
                for item in all_items
                if search in item.name or search in item.student_no
            ]

        all_items.sort(key=lambda x: x.student_no)

        return OcrProgressResponse(
            confirmed_student_count=confirmed_student_count,
            total_student_count=len(matched_sheets),
            students=all_items,
        )

    def list_ocr_results(
        self, student_id: int, member_id: int
    ) -> list[OcrResultResponse]:
        """학생 한 명의 문제별 OCR 결과 목록을 조회한다.

        Args:
            student_id: 대상 학생 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제 정보가 포함된 OCR 결과 목록

        Raises:
            StudentNotFoundError: 학생이 없거나 접근 권한이 없는 경우
        """
        student = self.student_repo.get_by_id(student_id)
        if not student:
            raise StudentNotFoundError()
        exam = self.exam_repo.get_accessible(student.exam_id, member_id)
        if not exam:
            raise StudentNotFoundError()

        results = self.ocr_result_repo.list_by_student(student_id, exam.layout_mode)
        problem_map = self.problem_repo.map_by_ids(
            [region.problem_id for _, region in results]
        )
        return [
            _to_response(ocr, region, problem_map[region.problem_id])
            for ocr, region in results
        ]

    def update_ocr_result(
        self, ocr_result_id: int, member_id: int, request: OcrResultUpdateRequest
    ) -> OcrResultResponse:
        """OCR 결과 텍스트/선택지를 수정한다.

        전송된 필드만 갱신한다.

        Args:
            ocr_result_id: 수정할 OCR 결과 ID
            member_id: 요청한 사용자 ID
            request: 변경할 OCR 필드 (미전송 필드는 무시)

        Returns:
            수정된 OCR 결과

        Raises:
            OcrResultNotFoundError: OCR 결과가 없거나 접근 권한이 없는 경우
        """
        ocr_result, region = self._get_ocr_result_or_raise(ocr_result_id, member_id)
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        updates = request.model_dump(exclude_unset=True)
        ocr_result = self.ocr_result_repo.update(ocr_result, **updates)
        return self._build_ocr_response(ocr_result, region, sheet.exam_id)

    def confirm_ocr_result(
        self, ocr_result_id: int, member_id: int
    ) -> OcrResultResponse:
        """OCR 결과를 검수 완료(REVIEWED) 상태로 확정한다.

        Args:
            ocr_result_id: 확정할 OCR 결과 ID
            member_id: 요청한 사용자 ID

        Returns:
            확정된 OCR 결과

        Raises:
            OcrResultNotFoundError: OCR 결과가 없거나 접근 권한이 없는 경우
        """
        ocr_result, region = self._get_ocr_result_or_raise(ocr_result_id, member_id)
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        ocr_result = self.ocr_result_repo.update(ocr_result, status=OCRStatus.REVIEWED)
        return self._build_ocr_response(ocr_result, region, sheet.exam_id)

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

    def _get_ocr_result_or_raise(
        self, ocr_result_id: int, member_id: int
    ) -> tuple[OCRResult, AnswerRegion]:
        """OCR 결과와 그 영역을 조회하고, 접근 권한이 없으면 예외를 던진다.

        결과·영역·답안지·시험 접근 권한을 확인하고, 영역의 레이아웃 모드가 시험의 현재
        모드와 다르면 존재를 숨긴다.

        Args:
            ocr_result_id: 조회할 OCR 결과 ID
            member_id: 요청한 사용자 ID

        Returns:
            OCR 결과와 대응 답안 영역의 튜플

        Raises:
            OcrResultNotFoundError: 결과·영역·답안지가 없거나 접근 권한이 없는 경우
        """
        ocr_result = self.ocr_result_repo.get_by_id(ocr_result_id)
        if not ocr_result:
            raise OcrResultNotFoundError()
        region = self.answer_region_repo.get_by_id(ocr_result.answer_region_id)
        if not region:
            raise OcrResultNotFoundError()
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        if not sheet:
            raise OcrResultNotFoundError()
        exam = self.exam_repo.get_accessible(sheet.exam_id, member_id)
        if not exam or region.layout_mode != exam.layout_mode:
            raise OcrResultNotFoundError()
        return ocr_result, region

    def _build_ocr_response(
        self, ocr_result: OCRResult, region: AnswerRegion, exam_id: int
    ) -> OcrResultResponse:
        """OCR 결과를 응답으로 변환하고 시험 갱신 시각을 찍는다.

        Args:
            ocr_result: 변환할 OCR 결과
            region: OCR 결과가 속한 답안 영역
            exam_id: 갱신 시각을 찍을 시험 ID

        Returns:
            문제 정보가 포함된 OCR 결과 응답
        """
        problem = self.problem_repo.get_by_id(region.problem_id)
        self.exam_repo.touch(exam_id)
        return _to_response(ocr_result, region, problem)


def _to_response(
    ocr_result: OCRResult, region: AnswerRegion, problem: Problem
) -> OcrResultResponse:
    """OCR 결과·영역·문제를 합쳐 응답 스키마로 변환한다.

    저장된 bbox·폴리곤 JSON을 각각 `Region`·`Point` 스키마로 복원한다.

    Args:
        ocr_result: 변환할 OCR 결과
        region: OCR 결과가 속한 답안 영역
        problem: 영역이 가리키는 문제

    Returns:
        문제 정보와 좌표가 포함된 OCR 결과 응답
    """
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
        polygon_points=(
            [Point(**p) for p in region.polygon_points]
            if region.polygon_points
            else None
        ),
    )


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return OcrService(
        OcrResultRepository(db),
        AnswerRegionRepository(db),
        AnswerSheetRepository(db),
        ExamRepository(db),
        StudentRepository(db),
        ProblemRepository(db),
        JobRepository(db),
    )
