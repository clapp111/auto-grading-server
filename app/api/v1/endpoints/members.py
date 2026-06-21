from fastapi import APIRouter, Depends

from app.core.security import get_current_member
from app.infrastructure.storage.url import get_file_url
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.member import MemberResponse

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/me", response_model=ApiResponse[MemberResponse])
async def get_me(
    current_member: Member = Depends(get_current_member),
) -> ApiResponse[MemberResponse]:
    member_response = MemberResponse.model_validate(
        current_member, update={"profile_url": get_file_url(current_member.profile_key)}
    )
    return ApiResponse(data=member_response)
