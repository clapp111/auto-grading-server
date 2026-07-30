from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.grade import (
    GradeBulkConfirmResponse,
    GradeCreateRequest,
    GradeResponse,
    GradeUpdateRequest,
    GradingProgressResponse,
)
from app.schemas.job import JobStartedResponse
from app.services.grade import GradeService, get_grade_service

router = APIRouter(tags=["grades"])


@router.get(
    "/exams/{exam_id}/grading/progress",
    response_model=ApiResponse[GradingProgressResponse],
)
async def get_grading_progress(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[GradingProgressResponse]:
    return ApiResponse(
        data=service.get_grading_progress(exam_id, current_member.member_id)
    )


@router.post(
    "/exams/{exam_id}/problems/{problem_id}/grade/run",
    status_code=202,
    response_model=ApiResponse[JobStartedResponse],
)
async def run_grade(
    exam_id: int,
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(
        data=service.run_grade(exam_id, problem_id, current_member.member_id)
    )


@router.get(
    "/problems/{problem_id}/grades", response_model=ApiResponse[list[GradeResponse]]
)
async def list_grades(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[list[GradeResponse]]:
    return ApiResponse(data=service.list_grades(problem_id, current_member.member_id))


@router.patch("/grades/{grade_id}", response_model=ApiResponse[GradeResponse])
async def update_grade(
    grade_id: int,
    request: GradeUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[GradeResponse]:
    return ApiResponse(
        data=service.update_grade(grade_id, current_member.member_id, request)
    )


@router.post("/grades/{grade_id}/confirm", response_model=ApiResponse[GradeResponse])
async def confirm_grade(
    grade_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[GradeResponse]:
    return ApiResponse(data=service.confirm_grade(grade_id, current_member.member_id))


@router.post(
    "/problems/{problem_id}/grades/confirm-all",
    response_model=ApiResponse[GradeBulkConfirmResponse],
)
async def confirm_all_grades(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[GradeBulkConfirmResponse]:
    return ApiResponse(
        data=service.confirm_all_grades(problem_id, current_member.member_id)
    )


@router.delete("/problems/{problem_id}/grades", status_code=204)
async def delete_grades(
    problem_id: int,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> Response:
    service.delete_grades(problem_id, current_member.member_id)
    return Response(status_code=204)


@router.post(
    "/problems/{problem_id}/students/{student_id}/grades",
    response_model=ApiResponse[GradeResponse],
)
async def create_grade(
    problem_id: int,
    student_id: int,
    request: GradeCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: GradeService = Depends(get_grade_service),
) -> ApiResponse[GradeResponse]:
    return ApiResponse(
        data=service.create_grade(
            problem_id, student_id, current_member.member_id, request
        )
    )
