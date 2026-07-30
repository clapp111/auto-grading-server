from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.job import JobStartedResponse
from app.schemas.rubric import (
    RubricCreateRequest,
    RubricResponse,
    RubricSaveRequest,
    RubricUpdateRequest,
)
from app.services.rubric import RubricService, get_rubric_service

router = APIRouter(tags=["rubrics"])


@router.post(
    "/problems/{problem_id}/rubric/suggest",
    status_code=202,
    response_model=ApiResponse[JobStartedResponse],
)
async def suggest_rubric(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(
        data=service.suggest_rubric(problem_id, current_member.member_id)
    )


@router.get(
    "/problems/{problem_id}/rubric", response_model=ApiResponse[list[RubricResponse]]
)
async def get_rubric(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> ApiResponse[list[RubricResponse]]:
    return ApiResponse(data=service.get_rubric(problem_id, current_member.member_id))


@router.put(
    "/problems/{problem_id}/rubric", response_model=ApiResponse[list[RubricResponse]]
)
async def save_rubric(
    problem_id: int,
    request: RubricSaveRequest,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> ApiResponse[list[RubricResponse]]:
    return ApiResponse(
        data=service.save_rubric(problem_id, current_member.member_id, request)
    )


@router.post(
    "/problems/{problem_id}/rubric/criteria",
    status_code=201,
    response_model=ApiResponse[RubricResponse],
)
async def create_criterion(
    problem_id: int,
    request: RubricCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> ApiResponse[RubricResponse]:
    return ApiResponse(
        data=service.create_criterion(problem_id, current_member.member_id, request)
    )


@router.patch("/rubrics/{rubric_id}", response_model=ApiResponse[RubricResponse])
async def update_criterion(
    rubric_id: int,
    request: RubricUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> ApiResponse[RubricResponse]:
    return ApiResponse(
        data=service.update_criterion(rubric_id, current_member.member_id, request)
    )


@router.delete("/rubrics/{rubric_id}", status_code=204)
async def delete_criterion(
    rubric_id: int,
    current_member: Member = Depends(get_current_member),
    service: RubricService = Depends(get_rubric_service),
) -> Response:
    service.delete_criterion(rubric_id, current_member.member_id)
    return Response(status_code=204)
