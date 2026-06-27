from pydantic import BaseModel, EmailStr, Field

from app.enums.affiliation_role import AffiliationRole
from app.schemas.member import MemberResponse


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    affiliation: str | None = None
    affiliation_role: AffiliationRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    member: MemberResponse
