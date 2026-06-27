from pydantic import BaseModel, Field

from app.enums.affiliation_role import AffiliationRole
from app.enums.role import Role


class MemberResponse(BaseModel):
    member_id: int
    email: str
    name: str
    affiliation: str | None
    affiliation_role: AffiliationRole
    role: Role
    profile_url: str | None = None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    affiliation: str | None = None
    affiliation_role: AffiliationRole | None = None
    profile_url: str | None = None


class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
