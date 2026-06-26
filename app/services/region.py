from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AnswerRegionNotFoundError, AnswerSheetNotFoundError, ExamNotFoundError
from app.db.session import get_db
from app.enums.job_type import JobType
from app.enums.layout_mode import LayoutMode
from app.models.answer_region import AnswerRegion
from app.repositories.answer_region import AnswerRegionRepository
from app.repositories.answer_sheet import AnswerSheetRepository
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
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
        job_repo: JobRepository,
    ):
        self.answer_region_repo = answer_region_repo
        self.answer_sheet_repo = answer_sheet_repo
        self.exam_repo = exam_repo
        self.job_repo = job_repo

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return exam

    def _get_region_or_raise(self, answer_region_id: int, member_id: int) -> AnswerRegion:
        region = self.answer_region_repo.get_by_id(answer_region_id)
        if not region:
            raise AnswerRegionNotFoundError()
        sheet = self.answer_sheet_repo.get_by_id(region.answer_sheet_id)
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        if not exam or exam.member_id != member_id:
            raise AnswerRegionNotFoundError()
        return region

    def list_regions(self, answer_sheet_id: int, member_id: int) -> list[AnswerRegionResponse]:
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        if not exam or exam.member_id != member_id:
            raise AnswerSheetNotFoundError()
        regions = self.answer_region_repo.list_by_answer_sheet(answer_sheet_id)
        return [_to_response(r) for r in regions]

    def create_region(self, answer_sheet_id: int, member_id: int, request: AnswerRegionCreateRequest) -> AnswerRegionResponse:
        sheet = self.answer_sheet_repo.get_by_id(answer_sheet_id)
        if not sheet:
            raise AnswerSheetNotFoundError()
        exam = self.exam_repo.get_by_id(sheet.exam_id)
        if not exam or exam.member_id != member_id:
            raise AnswerSheetNotFoundError()

        region = self.answer_region_repo.create(
            answer_sheet_id=answer_sheet_id,
            problem_id=request.problem_id,
            shape=request.shape,
            layout_mode=exam.layout_mode,
            bbox_region=request.bbox_region.model_dump() if request.bbox_region else None,
            polygon_points=[p.model_dump() for p in request.polygon_points] if request.polygon_points else None,
        )
        region = self.answer_region_repo.get_by_id(region.answer_region_id)
        return _to_response(region)

    def update_region(self, answer_region_id: int, member_id: int, request: AnswerRegionUpdateRequest) -> AnswerRegionResponse:
        region = self._get_region_or_raise(answer_region_id, member_id)

        updates = {}
        data = request.model_dump(exclude_unset=True)
        if "problem_id" in data:
            updates["problem_id"] = data["problem_id"]
        if "shape" in data:
            updates["shape"] = data["shape"]
        if "bbox_region" in data:
            updates["bbox_region"] = data["bbox_region"]
        if "polygon_points" in data:
            updates["polygon_points"] = data["polygon_points"]

        self.answer_region_repo.update(region, **updates)
        region = self.answer_region_repo.get_by_id(answer_region_id)
        return _to_response(region)

    def delete_region(self, answer_region_id: int, member_id: int) -> None:
        region = self._get_region_or_raise(answer_region_id, member_id)
        self.answer_region_repo.delete(region)

    def save_template(self, exam_id: int, member_id: int, request: RegionTemplateRequest) -> list[AnswerRegionResponse]:
        self._get_exam_or_raise(exam_id, member_id)

        sheets = sorted(self.answer_sheet_repo.list_by_exam(exam_id), key=lambda s: s.answer_sheet_id)
        if not sheets:
            raise AnswerSheetNotFoundError()

        first_sheet = sheets[0]
        self.answer_region_repo.delete_all_by_answer_sheet(first_sheet.answer_sheet_id)

        for item in request.regions:
            self.answer_region_repo.create(
                answer_sheet_id=first_sheet.answer_sheet_id,
                problem_id=item.problem_id,
                shape=item.shape,
                layout_mode=LayoutMode.FIXED,
                bbox_region=item.bbox_region.model_dump() if item.bbox_region else None,
                polygon_points=[p.model_dump() for p in item.polygon_points] if item.polygon_points else None,
            )

        regions = self.answer_region_repo.list_by_answer_sheet(first_sheet.answer_sheet_id)
        return [_to_response(r) for r in regions]

    def apply_template(self, exam_id: int, member_id: int) -> JobStartedResponse:
        from app.workers.region_tasks import apply_region_template

        self._get_exam_or_raise(exam_id, member_id)

        job = self.job_repo.create(
            exam_id=exam_id,
            type=JobType.REGION_TEMPLATE_APPLY,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id},
                "source": {"trigger": "api", "endpoint": f"/api/v1/exams/{exam_id}/regions/apply-template"},
            },
        )
        apply_region_template.delay(job.job_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)


def _to_response(region: AnswerRegion) -> AnswerRegionResponse:
    return AnswerRegionResponse(
        answer_region_id=region.answer_region_id,
        answer_sheet_id=region.answer_sheet_id,
        problem_id=region.problem_id,
        problem_label=region.problem.label,
        shape=region.shape,
        bbox_region=Region(**region.bbox_region) if region.bbox_region else None,
        polygon_points=[Point(**p) for p in region.polygon_points] if region.polygon_points else None,
        layout_mode=region.layout_mode,
    )


def get_region_service(db: Session = Depends(get_db)) -> RegionService:
    return RegionService(
        AnswerRegionRepository(db),
        AnswerSheetRepository(db),
        ExamRepository(db),
        JobRepository(db),
    )
