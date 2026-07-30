from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.result import (
    ExamResultResponse,
    ExamStatisticsResponse,
    StudentDetailResultResponse,
)
from app.services.result import ResultService, get_result_service

router = APIRouter(tags=["results"])


@router.get("/exams/{exam_id}/results", response_model=ApiResponse[ExamResultResponse])
async def get_exam_results(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ResultService = Depends(get_result_service),
) -> ApiResponse[ExamResultResponse]:
    return ApiResponse(data=service.get_exam_results(exam_id, current_member.member_id))


@router.get(
    "/exams/{exam_id}/results/statistics",
    response_model=ApiResponse[ExamStatisticsResponse],
)
async def get_statistics(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ResultService = Depends(get_result_service),
) -> ApiResponse[ExamStatisticsResponse]:
    return ApiResponse(data=service.get_statistics(exam_id, current_member.member_id))


@router.get(
    "/exams/{exam_id}/students/{student_id}/result",
    response_model=ApiResponse[StudentDetailResultResponse],
)
async def get_student_result(
    exam_id: int,
    student_id: int,
    current_member: Member = Depends(get_current_member),
    service: ResultService = Depends(get_result_service),
) -> ApiResponse[StudentDetailResultResponse]:
    return ApiResponse(
        data=service.get_student_result(student_id, exam_id, current_member.member_id)
    )


@router.get("/exams/{exam_id}/results/export")
async def export_results_csv(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ResultService = Depends(get_result_service),
) -> StreamingResponse:
    content, filename = service.export_results_csv(exam_id, current_member.member_id)
    encoded_filename = quote(filename, safe="", encoding="utf-8")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )
