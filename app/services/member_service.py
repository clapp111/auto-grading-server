from app.infrastructure.storage.url import get_file_url
from app.models.member import Member
from app.schemas.member import MemberResponse


class MemberService:
    def to_response(self, member: Member) -> MemberResponse:
        return MemberResponse.model_validate(member).model_copy(
            update={"profile_url": get_file_url(member.profile_key)}
        )


def get_member_service() -> MemberService:
    return MemberService()
