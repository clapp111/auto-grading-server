from fastapi import APIRouter, Depends

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.job import JobStartedResponse
from app.schemas.model_answer import ModelAnswerOcrRequest, ModelAnswerResponse, ModelAnswerUpdateRequest
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse
from app.services.model_answer import ModelAnswerService, get_model_answer_service

router = APIRouter(tags=["model-answer"])


@router.post("/exams/{exam_id}/model-answer", status_code=201, response_model=ApiResponse[PresignedUrlResponse])
async def issue_model_answer_url(
    exam_id: int,
    request: PresignedUrlRequest,
    current_member: Member = Depends(get_current_member),
    service: ModelAnswerService = Depends(get_model_answer_service),
) -> ApiResponse[PresignedUrlResponse]:
    return ApiResponse(data=service.issue_model_answer_url(exam_id, current_member.member_id, request))


@router.get("/exams/{exam_id}/model-answers", response_model=ApiResponse[list[ModelAnswerResponse]])
async def list_model_answers(
    exam_id: int,
    current_member: Member = Depends(get_current_member),
    service: ModelAnswerService = Depends(get_model_answer_service),
) -> ApiResponse[list[ModelAnswerResponse]]:
    return ApiResponse(data=service.list_model_answers(exam_id, current_member.member_id))


@router.post("/problems/{problem_id}/model-answer/ocr", status_code=202, response_model=ApiResponse[JobStartedResponse])
async def run_model_answer_ocr(
    problem_id: int,
    request: ModelAnswerOcrRequest,
    current_member: Member = Depends(get_current_member),
    service: ModelAnswerService = Depends(get_model_answer_service),
) -> ApiResponse[JobStartedResponse]:
    return ApiResponse(data=service.run_ocr(problem_id, current_member.member_id, request))


@router.put("/problems/{problem_id}/model-answer", response_model=ApiResponse[ModelAnswerResponse])
async def update_model_answer(
    problem_id: int,
    request: ModelAnswerUpdateRequest,
    current_member: Member = Depends(get_current_member),
    service: ModelAnswerService = Depends(get_model_answer_service),
) -> ApiResponse[ModelAnswerResponse]:
    return ApiResponse(data=service.update_model_answer(problem_id, current_member.member_id, request))
