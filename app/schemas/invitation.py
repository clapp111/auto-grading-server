from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.enums.invitation_status import InvitationStatus


class InvitationCreateRequest(BaseModel):
    email: EmailStr


class InvitationResponse(BaseModel):
    invitation_id: int
    exam_id: int
    exam_name: str
    inviter_name: str
    inviter_email: EmailStr
    status: InvitationStatus
    created_at: datetime
    responded_at: datetime | None


class ExamInvitationResponse(BaseModel):
    invitation_id: int
    exam_id: int
    invitee_member_id: int
    invitee_name: str
    invitee_email: EmailStr
    status: InvitationStatus
    created_at: datetime
    responded_at: datetime | None


class ExamMemberResponse(BaseModel):
    member_id: int
    name: str
    email: EmailStr
    is_owner: bool
    joined_at: datetime | None
