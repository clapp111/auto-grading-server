from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.job import JobStartedResponse
from app.schemas.ocr_result import (
    OcrProgressResponse,
    OcrResultResponse,
    OcrResultUpdateRequest,
)
from app.services.ocr import OcrService, get_ocr_service

router = APIRouter(tags=["ocr-results"])


@router.post(
    "/exams/{exam_id}/ocr/run",
    status_code=202,
    response_model=ApiResponse[JobStartedResponse],
)
async def run_ocr(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: OcrService = Depends(get_ocr_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(data=service.run_ocr(exam_id, current_member.member_id))


@router.get(
    "/exams/{exam_id}/ocr/progress", response_model=ApiResponse[OcrProgressResponse]
)
async def get_ocr_progress(
    exam_id: int,
    search: str | None = Query(default=None),
    current_member: Member = Depends(get_current_member),
    service: OcrService = Depends(get_ocr_service),
) -> ApiResponse[OcrProgressResponse]:
    return ApiResponse(
        data=service.get_progress(exam_id, current_member.member_id, search)
    )


@router.get(
    "/students/{student_id}/ocr-results",
    response_model=ApiResponse[list[OcrResultResponse]],
)
async def list_ocr_results(
    student_id: int,
    current_member: Member = Depends(get_current_member),
    service: OcrService = Depends(get_ocr_service),
) -> ApiResponse[list[OcrResultResponse]]:
    return ApiResponse(
        data=service.list_ocr_results(student_id, current_member.member_id)
    )


@router.patch(
    "/ocr-results/{ocr_result_id}", response_model=ApiResponse[OcrResultResponse]
)
async def update_ocr_result(
    ocr_result_id: int,
    request: OcrResultUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: OcrService = Depends(get_ocr_service),
) -> ApiResponse[OcrResultResponse]:
    return ApiResponse(
        data=service.update_ocr_result(ocr_result_id, current_member.member_id, request)
    )


@router.post(
    "/ocr-results/{ocr_result_id}/confirm",
    response_model=ApiResponse[OcrResultResponse],
)
async def confirm_ocr_result(
    ocr_result_id: int,
    current_member: Member = Depends(get_current_member),
    service: OcrService = Depends(get_ocr_service),
) -> ApiResponse[OcrResultResponse]:
    return ApiResponse(
        data=service.confirm_ocr_result(ocr_result_id, current_member.member_id)
    )
