from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.answer_region import (
    AnswerRegionCreateRequest,
    AnswerRegionResponse,
    AnswerRegionUpdateRequest,
)
from app.schemas.common import ApiResponse
from app.services.region import RegionService, get_region_service

router = APIRouter(tags=["answer-regions"])


@router.get(
    "/answer-sheets/{answer_sheet_id}/regions",
    response_model=ApiResponse[list[AnswerRegionResponse]],
)
async def list_regions(
    answer_sheet_id: int,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> ApiResponse[list[AnswerRegionResponse]]:
    return ApiResponse(
        data=service.list_regions(answer_sheet_id, current_member.member_id)
    )


@router.post(
    "/answer-sheets/{answer_sheet_id}/regions",
    status_code=201,
    response_model=ApiResponse[AnswerRegionResponse],
)
async def create_region(
    answer_sheet_id: int,
    request: AnswerRegionCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> ApiResponse[AnswerRegionResponse]:
    return ApiResponse(
        data=service.create_region(answer_sheet_id, current_member.member_id, request)
    )


@router.patch(
    "/answer-regions/{answer_region_id}",
    response_model=ApiResponse[AnswerRegionResponse],
)
async def update_region(
    answer_region_id: int,
    request: AnswerRegionUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> ApiResponse[AnswerRegionResponse]:
    return ApiResponse(
        data=service.update_region(answer_region_id, current_member.member_id, request)
    )


@router.delete("/answer-regions/{answer_region_id}", status_code=204)
async def delete_region(
    answer_region_id: int,
    current_member: Member = Depends(get_current_member),
    service: RegionService = Depends(get_region_service),
) -> Response:
    service.delete_region(answer_region_id, current_member.member_id)
    return Response(status_code=204)
