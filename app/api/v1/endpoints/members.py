from fastapi import APIRouter, Depends

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.member import MemberResponse
from app.services.member_service import MemberService, get_member_service

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/me", response_model=ApiResponse[MemberResponse])
async def get_me(
    current_member: Member = Depends(get_current_member),
    service: MemberService = Depends(get_member_service),
) -> ApiResponse[MemberResponse]:
    return ApiResponse(data=service.to_response(current_member))
