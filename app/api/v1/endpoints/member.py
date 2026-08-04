from fastapi import APIRouter, Depends

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.member import (
    MemberResponse,
    UpdatePasswordRequest,
    UpdateProfileRequest,
)
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse
from app.services.member import MemberService, get_member_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/me", response_model=ApiResponse[MemberResponse])
async def get_me(
    current_member: Member = Depends(get_current_member),
    service: MemberService = Depends(get_member_service),
) -> ApiResponse[MemberResponse]:
    return ApiResponse(data=service.to_response(current_member))


@router.patch("/me", response_model=ApiResponse[MemberResponse])
async def update_profile(
    request: UpdateProfileRequest,
    current_member: Member = Depends(get_current_member),
    service: MemberService = Depends(get_member_service),
) -> ApiResponse[MemberResponse]:
    return ApiResponse(data=service.update_profile(current_member, request))


@router.patch("/me/password", status_code=204)
async def update_password(
    request: UpdatePasswordRequest,
    current_member: Member = Depends(get_current_member),
    service: MemberService = Depends(get_member_service),
) -> None:
    service.update_password(current_member, request)


@router.post(
    "/me/profile/upload",
    status_code=201,
    response_model=ApiResponse[PresignedUrlResponse],
)
async def issue_profile_upload_url(
    request: PresignedUrlRequest,
    current_member: Member = Depends(get_current_member),
    service: MemberService = Depends(get_member_service),
) -> ApiResponse[PresignedUrlResponse]:
    return ApiResponse(
        data=service.issue_profile_upload_url(current_member.member_id, request)
    )
