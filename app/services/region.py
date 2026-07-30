from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AnswerRegionNotFoundError,
    AnswerSheetNotFoundError,
    ExamNotFoundError,
)
from app.db.session import get_db
from app.enums.job_type import JobType
from app.models.answer_region import AnswerRegion
from app.repositories.answer_region import AnswerRegionRepository
from app.repositories.answer_sheet import AnswerSheetRepository
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.repositories.problem import ProblemRepository
from app.schemas.answer_region import (
    AnswerRegionCreateRequest,
    AnswerRegionResponse,
    AnswerRegionUpdateRequest,
    RegionTemplateRequest,
)
from app.schemas.common import Point, Region
from app.schemas.job import JobStartedResponse


class RegionService:
    def __init__(
        self,
        answer_region_repo: AnswerRegionRepository,
        answer_sheet_repo: AnswerSheetRepository,
        exam_repo: ExamRepository,
        problem_repo: ProblemRepository,
        job_repo: JobRepository,
    ):
        self.answer_region_repo = answer_region_repo
        self.answer_sheet_repo = answer_sheet_repo
        self.exam_repo = exam_repo
        self.problem_repo = problem_repo
        self.job_repo = job_repo

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def list_regions(
        self, answer_sheet_id: int, member_id: int
    ) -> list[AnswerRegionResponse]:
        """답안지의 문제별 답안 영역 목록을 조회한다.

        시험의 현재 레이아웃 모드에 해당하는 영역만 반환한다.

        Args:
            answer_sheet_id: 조회할 답안지 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제 라벨이 포함된 답안 영역 목록

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_accessible(sheet.exam_id, member_id)
        if not exam:
            raise AnswerSheetNotFoundError()
        regions = self.answer_region_repo.list_by_answer_sheet(
            answer_sheet_id, exam.layout_mode
        )
        problem_map = self.problem_repo.map_by_ids([r.problem_id for r in regions])
        return [_to_response(r, problem_map[r.problem_id].label) for r in regions]

    def create_region(
        self, answer_sheet_id: int, member_id: int, request: AnswerRegionCreateRequest
    ) -> AnswerRegionResponse:
        """답안지에 문제별 답안 영역을 지정한다.

        같은 문제·레이아웃 모드에 이미 영역이 있으면 갱신하고, 없으면 새로 만든다.

        Args:
            answer_sheet_id: 대상 답안지 ID
            member_id: 요청한 사용자 ID
            request: 문제 ID·도형·bbox·폴리곤 좌표

        Returns:
            생성 또는 갱신된 답안 영역

        Raises:
            AnswerSheetNotFoundError: 답안지가 없거나 접근 권한이 없는 경우
        """
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_accessible(sheet.exam_id, member_id)
        if not exam:
            raise AnswerSheetNotFoundError()
        exam_id = sheet.exam_id

        updates = {
            "problem_id": request.problem_id,
            "shape": request.shape,
            "bbox_region": (
                request.bbox_region.model_dump() if request.bbox_region else None
            ),
            "polygon_points": (
                [p.model_dump() for p in request.polygon_points]
                if request.polygon_points
                else None
            ),
        }
        region = self.answer_region_repo.get_by_sheet_problem_and_mode(
            answer_sheet_id=answer_sheet_id,
            problem_id=request.problem_id,
            layout_mode=exam.layout_mode,
        )
        if region:
            region = self.answer_region_repo.update(region, **updates)
        else:
            region = self.answer_region_repo.create(
                answer_sheet_id=answer_sheet_id,
                layout_mode=exam.layout_mode,
                **updates,
            )
        problem = self.problem_repo.get_by_id(region.problem_id)
        self.exam_repo.touch(exam_id)
        return _to_response(region, problem.label)

    def update_region(
        self, answer_region_id: int, member_id: int, request: AnswerRegionUpdateRequest
    ) -> AnswerRegionResponse:
        """답안 영역을 수정한다.

        전송된 필드만 갱신한다.

        Args:
            answer_region_id: 수정할 답안 영역 ID
            member_id: 요청한 사용자 ID
            request: 변경할 영역 필드 (미전송 필드는 무시)

        Returns:
            수정된 답안 영역

        Raises:
            AnswerRegionNotFoundError: 영역이 없거나 접근 권한이 없는 경우
        """
        region = self._get_region_or_raise(answer_region_id, member_id)
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        exam_id = sheet.exam_id

        updates = request.model_dump(exclude_unset=True)
        region = self.answer_region_repo.update(region, **updates)
        problem = self.problem_repo.get_by_id(region.problem_id)
        self.exam_repo.touch(exam_id)
        return _to_response(region, problem.label)

    def delete_region(self, answer_region_id: int, member_id: int) -> None:
        """답안 영역을 삭제한다.

        Args:
            answer_region_id: 삭제할 답안 영역 ID
            member_id: 요청한 사용자 ID

        Raises:
            AnswerRegionNotFoundError: 영역이 없거나 접근 권한이 없는 경우
        """
        region = self._get_region_or_raise(answer_region_id, member_id)
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        exam_id = sheet.exam_id
        self.answer_region_repo.delete(region)
        self.exam_repo.touch(exam_id)

    def save_template(
        self, exam_id: int, member_id: int, request: RegionTemplateRequest
    ) -> list[AnswerRegionResponse]:
        """첫 번째 답안지에 영역 템플릿을 저장한다.

        답안지들 중 가장 앞선 답안지를 템플릿 기준으로 삼아 기존 영역을 지우고 새로
        저장한다. 이후 `apply_template`으로 나머지 답안지에 복제한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID
            request: 저장할 영역 목록

        Returns:
            템플릿 답안지에 저장된 영역 목록

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            AnswerSheetNotFoundError: 시험에 답안지가 하나도 없는 경우
        """
        exam = self._get_exam_or_raise(exam_id, member_id)

        sheets = sorted(
            self.answer_sheet_repo.list_by_exam(exam_id),
            key=lambda s: s.answer_sheet_id,
        )
        if not sheets:
            raise AnswerSheetNotFoundError()

        first_sheet = sheets[0]
        self.answer_region_repo.delete_all_by_answer_sheet(
            first_sheet.answer_sheet_id, exam.layout_mode
        )

        for item in request.regions:
            self.answer_region_repo.create(
                answer_sheet_id=first_sheet.answer_sheet_id,
                problem_id=item.problem_id,
                shape=item.shape,
                layout_mode=exam.layout_mode,
                bbox_region=item.bbox_region.model_dump() if item.bbox_region else None,
                polygon_points=(
                    [p.model_dump() for p in item.polygon_points]
                    if item.polygon_points
                    else None
                ),
            )

        regions = self.answer_region_repo.list_by_answer_sheet(
            first_sheet.answer_sheet_id, exam.layout_mode
        )
        problem_map = self.problem_repo.map_by_ids([r.problem_id for r in regions])
        self.exam_repo.touch(exam_id)
        return [_to_response(r, problem_map[r.problem_id].label) for r in regions]

    def apply_template(self, exam_id: int, member_id: int) -> JobStartedResponse:
        """영역 템플릿을 나머지 답안지에 복제하는 잡을 실행한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        from app.workers.region_tasks import apply_region_template

        self._get_exam_or_raise(exam_id, member_id)

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.REGION_TEMPLATE_APPLY,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/exams/{exam_id}/regions/apply-template",
                },
            },
        )
        apply_region_template.delay(job.job_id)
        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

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

    def _get_region_or_raise(
        self, answer_region_id: int, member_id: int
    ) -> AnswerRegion:
        """답안 영역을 조회하고, 없거나 접근 권한이 없으면 예외를 던진다.

        영역·답안지·시험 접근 권한을 확인하고, 영역의 레이아웃 모드가 시험의 현재 모드와
        다르면 존재를 숨긴다.

        Args:
            answer_region_id: 조회할 답안 영역 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 답안 영역

        Raises:
            AnswerRegionNotFoundError: 영역·답안지가 없거나 접근 권한이 없는 경우
        """
        region = self.answer_region_repo.get_by_id(answer_region_id)
        if not region:
            raise AnswerRegionNotFoundError()
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        if not sheet:
            raise AnswerRegionNotFoundError()
        exam = self.exam_repo.get_accessible(sheet.exam_id, member_id)
        if not exam or region.layout_mode != exam.layout_mode:
            raise AnswerRegionNotFoundError()
        return region


def _to_response(region: AnswerRegion, problem_label: str) -> AnswerRegionResponse:
    """답안 영역 엔티티를 응답 스키마로 변환한다.

    저장된 bbox·폴리곤 JSON을 각각 `Region`·`Point` 스키마로 복원한다.

    Args:
        region: 변환할 답안 영역
        problem_label: 영역이 가리키는 문제의 라벨

    Returns:
        문제 라벨과 좌표가 포함된 답안 영역 응답
    """
    return AnswerRegionResponse(
        answer_region_id=region.answer_region_id,
        answer_sheet_id=region.answer_sheet_id,
        problem_id=region.problem_id,
        problem_label=problem_label,
        shape=region.shape,
        bbox_region=Region(**region.bbox_region) if region.bbox_region else None,
        polygon_points=(
            [Point(**p) for p in region.polygon_points]
            if region.polygon_points
            else None
        ),
        layout_mode=region.layout_mode,
    )


def get_region_service(db: Session = Depends(get_db)) -> RegionService:
    return RegionService(
        AnswerRegionRepository(db),
        AnswerSheetRepository(db),
        ExamRepository(db),
        ProblemRepository(db),
        JobRepository(db),
    )
