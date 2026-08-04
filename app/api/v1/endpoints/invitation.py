from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.security import get_current_member
from app.enums.invitation_status import InvitationStatus
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.invitation import (
    ExamInvitationResponse,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.services.invitation import InvitationService, get_invitation_service

router = APIRouter(prefix="/invitations", tags=["invitations"])
exam_router = APIRouter(prefix="/exams", tags=["invitations"])


@router.get("", response_model=ApiResponse[list[InvitationResponse]])
async def list_invitations(
    status: InvitationStatus | None = Query(default=None),
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> ApiResponse[list[InvitationResponse]]:
    return ApiResponse(
        data=service.list_received_invitations(current_member.member_id, status)
    )


@router.post("/{invitation_id}/accept", status_code=204)
async def accept_invitation(
    invitation_id: int,
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> Response:
    service.accept_invitation(invitation_id, current_member.member_id)
    return Response(status_code=204)


@router.post("/{invitation_id}/decline", status_code=204)
async def decline_invitation(
    invitation_id: int,
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> Response:
    service.decline_invitation(invitation_id, current_member.member_id)
    return Response(status_code=204)


@router.delete("/{invitation_id}", status_code=204)
async def cancel_invitation(
    invitation_id: int,
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> Response:
    service.cancel_invitation(invitation_id, current_member.member_id)
    return Response(status_code=204)


@exam_router.post(
    "/{exam_id}/invitations",
    status_code=201,
    response_model=ApiResponse[ExamInvitationResponse],
)
async def create_invitation(
    exam_id: int,
    request: InvitationCreateRequest,
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> ApiResponse[ExamInvitationResponse]:
    return ApiResponse(
        data=service.create_invitation(exam_id, current_member.member_id, request)
    )


@exam_router.get(
    "/{exam_id}/invitations", response_model=ApiResponse[list[ExamInvitationResponse]]
)
async def list_exam_invitations(
    exam_id: int,
    status: InvitationStatus | None = Query(default=None),
    current_member: Member = Depends(get_current_member),
    service: InvitationService = Depends(get_invitation_service),
) -> ApiResponse[list[ExamInvitationResponse]]:
    return ApiResponse(
        data=service.list_exam_invitations(exam_id, current_member.member_id, status)
    )
