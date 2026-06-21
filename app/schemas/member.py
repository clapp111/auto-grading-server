from pydantic import BaseModel

from app.enums.affiliation_role import AffiliationRole
from app.enums.role import Role


class MemberResponse(BaseModel):
    member_id: int
    email: str
    affiliation: str | None
    affiliation_role: AffiliationRole
    role: Role
    profile_url: str | None

    model_config = {"from_attributes": True}
