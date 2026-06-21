from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.security import get_current_member
from app.enums.exam_status import ExamStatus
from app.models.member import Member
from app.schemas.common import ApiResponse, CursorMeta
from app.schemas.exam import ExamCreate, ExamResponse, ExamUpdate
from app.services.exam import ExamService, get_exam_service

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
    request: ExamCreate,
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
    request: ExamUpdate,
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
