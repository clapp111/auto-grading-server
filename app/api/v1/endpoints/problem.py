from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.job import JobStartedResponse
from app.schemas.problem import (
    ProblemCreateRequest,
    ProblemResponse,
    ProblemUpdateRequest,
)
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse
from app.services.problem import ProblemService, get_problem_service

router = APIRouter(tags=["problems"])


@router.post(
    "/exams/{exam_id}/problem-sheet",
    status_code=201,
    response_model=ApiResponse[PresignedUrlResponse],
)
async def issue_problem_sheet_url(
    exam_id: int,
    request: PresignedUrlRequest,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> ApiResponse[PresignedUrlResponse]:
    return ApiResponse(
        data=service.issue_problem_sheet_url(exam_id, current_member.member_id, request)
    )


@router.get(
    "/exams/{exam_id}/problems", response_model=ApiResponse[list[ProblemResponse]]
)
async def list_problems(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> ApiResponse[list[ProblemResponse]]:
    return ApiResponse(data=service.list_problems(exam_id, current_member.member_id))


@router.post(
    "/exams/{exam_id}/problems",
    status_code=201,
    response_model=ApiResponse[ProblemResponse],
)
async def create_problem(
    exam_id: int,
    request: ProblemCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> ApiResponse[ProblemResponse]:
    return ApiResponse(
        data=service.create_problem(exam_id, current_member.member_id, request)
    )


@router.patch("/problems/{problem_id}", response_model=ApiResponse[ProblemResponse])
async def update_problem(
    problem_id: int,
    request: ProblemUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> ApiResponse[ProblemResponse]:
    return ApiResponse(
        data=service.update_problem(problem_id, current_member.member_id, request)
    )


@router.post(
    "/problems/{problem_id}/ocr",
    status_code=202,
    response_model=ApiResponse[JobStartedResponse],
)
async def run_problem_ocr(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(
        data=service.run_problem_ocr(problem_id, current_member.member_id)
    )


@router.delete("/problems/{problem_id}", status_code=204)
async def delete_problem(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: ProblemService = Depends(get_problem_service),
) -> Response:
    service.delete_problem(problem_id, current_member.member_id)
    return Response(status_code=204)
