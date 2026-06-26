from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.security import get_current_member
from app.enums.exam_status import ExamStatus
from app.models.member import Member
from app.schemas.answer_region import AnswerRegionResponse, RegionTemplateRequest
from app.schemas.common import ApiResponse, CursorMeta
from app.schemas.exam import ExamCreateRequest, ExamResponse, ExamUpdateRequest
from app.schemas.job import JobStartedResponse
from app.services.exam import ExamService, get_exam_service
from app.services.region import RegionService, get_region_service

router = APIRouter(prefix="/exams", tags=["exams"])


@router.get("", response_model=ApiResponse[list[ExamResponse]])
async def list_exams(
    cursor: str | None = Query(default=None),
    size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    status: ExamStatus | None = Query(default=None),
    current_member: Member = Depends(get_current_member),
    service: ExamService = Depends(get_exam_service),
) -> ApiResponse[list[ExamResponse]]:
    items, meta = service.list_exams(current_member.member_id, cursor, size, search, status)
    return ApiResponse(data=items, meta=meta)


@router.post("", status_code=201, response_model=ApiResponse[ExamResponse])
async def create_exam(
    request: ExamCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: ExamService = Depends(get_exam_service),
) -> ApiResponse[ExamResponse]:
    return ApiResponse(data=service.create_exam(current_member.member_id, request))


@router.get("/{exam_id}", response_model=ApiResponse[ExamResponse])
async def get_exam(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ExamService = Depends(get_exam_service),
) -> ApiResponse[ExamResponse]:
    return ApiResponse(data=service.get_exam(exam_id, current_member.member_id))


@router.patch("/{exam_id}", response_model=ApiResponse[ExamResponse])
async def update_exam(
    exam_id: int,
    request: ExamUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: ExamService = Depends(get_exam_service),
) -> ApiResponse[ExamResponse]:
    return ApiResponse(data=service.update_exam(exam_id, current_member.member_id, request))


@router.delete("/{exam_id}", status_code=204)
async def delete_exam(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ExamService = Depends(get_exam_service),
) -> Response:
    service.delete_exam(exam_id, current_member.member_id)
    return Response(status_code=204)


@router.put("/{exam_id}/region-template", response_model=ApiResponse[list[AnswerRegionResponse]])
async def save_region_template(
    exam_id: int,
    request: RegionTemplateRequest,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> ApiResponse[list[AnswerRegionResponse]]:
    return ApiResponse(data=service.save_template(exam_id, current_member.member_id, request))


@router.post("/{exam_id}/regions/apply-template", status_code=202, response_model=ApiResponse[JobStartedResponse])
async def apply_region_template(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(data=service.apply_template(exam_id, current_member.member_id))
