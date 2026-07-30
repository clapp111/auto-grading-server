from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.enums.invitation_status import InvitationStatus
from app.models.exam import Exam
from app.models.invitation import Invitation
from app.models.member import Member


class InvitationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, invitation_id: int) -> Invitation | None:
        return self.db.get(Invitation, invitation_id)

    def find_pending(self, exam_id: int, invitee_member_id: int) -> Invitation | None:
        return (
            self.db.query(Invitation)
            .filter(
                Invitation.exam_id == exam_id,
                Invitation.invitee_member_id == invitee_member_id,
                Invitation.status == InvitationStatus.PENDING,
            )
            .first()
        )

    def list_received_with_context(self, invitee_member_id: int, status: InvitationStatus | None) -> list[tuple[Invitation, Exam, Member]]:
        q = (
            self.db.query(Invitation, Exam, Member)
            .join(Exam, Invitation.exam_id == Exam.exam_id)
            .join(Member, Invitation.inviter_member_id == Member.member_id)
            .filter(Invitation.invitee_member_id == invitee_member_id)
        )
        if status is not None:
            q = q.filter(Invitation.status == status)
        return q.order_by(Invitation.invitation_id.desc()).all()

    def list_by_exam_with_invitee(self, exam_id: int, status: InvitationStatus | None) -> list[tuple[Invitation, Member]]:
        q = (
            self.db.query(Invitation, Member)
            .join(Member, Invitation.invitee_member_id == Member.member_id)
            .filter(Invitation.exam_id == exam_id)
        )
        if status is not None:
            q = q.filter(Invitation.status == status)
        return q.order_by(Invitation.invitation_id.desc()).all()

    def create(self, exam_id: int, inviter_member_id: int, invitee_member_id: int) -> Invitation:
        invitation = Invitation(
            exam_id=exam_id,
            inviter_member_id=inviter_member_id,
            invitee_member_id=invitee_member_id,
            status=InvitationStatus.PENDING,
        )
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation

    def update_status(self, invitation: Invitation, status: InvitationStatus) -> Invitation:
        invitation.status = status
        invitation.responded_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation
