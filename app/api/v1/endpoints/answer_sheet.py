from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.answer_sheet import (
    AnswerSheetDownloadResponse,
    AnswerSheetPatchRequest,
    AnswerSheetResponse,
    IdRegionSaveRequest,
)
from app.schemas.common import ApiResponse
from app.schemas.job import JobStartedResponse
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse
from app.services.answer_sheet import AnswerSheetService, get_answer_sheet_service

router = APIRouter(tags=["answer-sheets"])


@router.post("/exams/{exam_id}/answer-sheets", status_code=201, response_model=ApiResponse[PresignedUrlResponse])
async def issue_answer_sheet_url(
    exam_id: int,
    request: PresignedUrlRequest,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> ApiResponse[PresignedUrlResponse]:
    return ApiResponse(data=service.issue_upload_url(exam_id, current_member.member_id, request))


@router.get("/exams/{exam_id}/answer-sheets", response_model=ApiResponse[list[AnswerSheetResponse]])
async def list_answer_sheets(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> ApiResponse[list[AnswerSheetResponse]]:
    return ApiResponse(data=service.list_answer_sheets(exam_id, current_member.member_id))


@router.delete("/answer-sheets/{answer_sheet_id}", status_code=204)
async def delete_answer_sheet(
    answer_sheet_id: int,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> Response:
    service.delete_answer_sheet(answer_sheet_id, current_member.member_id)
    return Response(status_code=204)


@router.post("/exams/{exam_id}/id-regions", status_code=202, response_model=ApiResponse[JobStartedResponse])
async def save_id_regions(
    exam_id: int,
    request: IdRegionSaveRequest,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(data=service.save_id_regions(exam_id, current_member.member_id, request))


@router.get("/answer-sheets/{answer_sheet_id}/download", response_model=ApiResponse[AnswerSheetDownloadResponse])
async def get_download_url(
    answer_sheet_id: int,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> ApiResponse[AnswerSheetDownloadResponse]:
    return ApiResponse(data=service.get_download_url(answer_sheet_id, current_member.member_id))


@router.patch("/answer-sheets/{answer_sheet_id}", response_model=ApiResponse[AnswerSheetResponse])
async def patch_answer_sheet(
    answer_sheet_id: int,
    request: AnswerSheetPatchRequest,
    current_member: Member = Depends(get_current_member),
    service: AnswerSheetService = Depends(get_answer_sheet_service),
) -> ApiResponse[AnswerSheetResponse]:
    return ApiResponse(data=service.patch_answer_sheet(answer_sheet_id, current_member.member_id, request))
