from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AlreadyExamMemberError,
    ExamNotFoundError,
    ExamOwnerRequiredError,
    InvitationAlreadyPendingError,
    InvitationAlreadyRespondedError,
    InvitationNotFoundError,
    MemberNotFoundError,
    SelfInvitationError,
)
from app.db.session import get_db
from app.enums.invitation_status import InvitationStatus
from app.models.exam import Exam
from app.models.invitation import Invitation
from app.models.member import Member
from app.repositories.exam import ExamRepository
from app.repositories.exam_member import ExamMemberRepository
from app.repositories.invitation import InvitationRepository
from app.repositories.member import MemberRepository
from app.schemas.invitation import (
    ExamInvitationResponse,
    ExamMemberResponse,
    InvitationCreateRequest,
    InvitationResponse,
)


class InvitationService:
    def __init__(
        self,
        repo: InvitationRepository,
        exam_repo: ExamRepository,
        exam_member_repo: ExamMemberRepository,
        member_repo: MemberRepository,
    ):
        self.repo = repo
        self.exam_repo = exam_repo
        self.exam_member_repo = exam_member_repo
        self.member_repo = member_repo

    def _get_owned_exam_or_raise(self, exam_id: int, member_id: int) -> Exam:
        # 참여자에게는 소유자 전용 동작임을 알려주고, 무관한 사용자에게는 시험 존재 자체를 숨긴다.
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        if exam.member_id != member_id:
            raise ExamOwnerRequiredError()
        return exam

    def _get_received_invitation_or_raise(self, invitation_id: int, member_id: int) -> Invitation:
        invitation = self.repo.get_by_id(invitation_id)
        if not invitation or invitation.invitee_member_id != member_id:
            raise InvitationNotFoundError()
        return invitation

    @staticmethod
    def _to_received_response(invitation: Invitation, exam: Exam, inviter: Member) -> InvitationResponse:
        return InvitationResponse(
            invitation_id=invitation.invitation_id,
            exam_id=exam.exam_id,
            exam_name=exam.name,
            inviter_name=inviter.name,
            inviter_email=inviter.email,
            status=invitation.status,
            created_at=invitation.created_at,
            responded_at=invitation.responded_at,
        )

    @staticmethod
    def _to_exam_invitation_response(invitation: Invitation, invitee: Member) -> ExamInvitationResponse:
        return ExamInvitationResponse(
            invitation_id=invitation.invitation_id,
            exam_id=invitation.exam_id,
            invitee_member_id=invitee.member_id,
            invitee_name=invitee.name,
            invitee_email=invitee.email,
            status=invitation.status,
            created_at=invitation.created_at,
            responded_at=invitation.responded_at,
        )

    def create_invitation(self, exam_id: int, member_id: int, request: InvitationCreateRequest) -> ExamInvitationResponse:
        self._get_owned_exam_or_raise(exam_id, member_id)

        invitee = self.member_repo.find_by_email(request.email)
        if not invitee:
            raise MemberNotFoundError()
        if invitee.member_id == member_id:
            raise SelfInvitationError()
        if self.exam_member_repo.exists(exam_id, invitee.member_id):
            raise AlreadyExamMemberError()
        if self.repo.find_pending(exam_id, invitee.member_id):
            raise InvitationAlreadyPendingError()

        invitation = self.repo.create(exam_id, member_id, invitee.member_id)
        return self._to_exam_invitation_response(invitation, invitee)

    def list_exam_invitations(self, exam_id: int, member_id: int, status: InvitationStatus | None) -> list[ExamInvitationResponse]:
        self._get_owned_exam_or_raise(exam_id, member_id)
        rows = self.repo.list_by_exam_with_invitee(exam_id, status)
        return [self._to_exam_invitation_response(inv, invitee) for inv, invitee in rows]

    def cancel_invitation(self, invitation_id: int, member_id: int) -> None:
        invitation = self.repo.get_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFoundError()
        exam = self.exam_repo.get_owned(invitation.exam_id, member_id)
        if not exam:
            raise InvitationNotFoundError()
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()
        self.repo.update_status(invitation, InvitationStatus.CANCELED)

    def list_received_invitations(self, member_id: int, status: InvitationStatus | None) -> list[InvitationResponse]:
        rows = self.repo.list_received_with_context(member_id, status)
        return [self._to_received_response(inv, exam, inviter) for inv, exam, inviter in rows]

    def accept_invitation(self, invitation_id: int, member_id: int) -> None:
        invitation = self._get_received_invitation_or_raise(invitation_id, member_id)
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()

        if not self.exam_member_repo.exists(invitation.exam_id, member_id):
            self.exam_member_repo.create(invitation.exam_id, member_id)
        self.repo.update_status(invitation, InvitationStatus.ACCEPTED)

    def decline_invitation(self, invitation_id: int, member_id: int) -> None:
        invitation = self._get_received_invitation_or_raise(invitation_id, member_id)
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()
        self.repo.update_status(invitation, InvitationStatus.DECLINED)

    def list_exam_members(self, exam_id: int, member_id: int) -> list[ExamMemberResponse]:
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()

        owner = self.member_repo.find_by_id(exam.member_id)
        items = [
            ExamMemberResponse(
                member_id=owner.member_id,
                name=owner.name,
                email=owner.email,
                is_owner=True,
                joined_at=exam.created_at,
            )
        ]
        for exam_member, member in self.exam_member_repo.list_with_member_by_exam(exam_id):
            items.append(
                ExamMemberResponse(
                    member_id=member.member_id,
                    name=member.name,
                    email=member.email,
                    is_owner=False,
                    joined_at=exam_member.created_at,
                )
            )
        return items

    def remove_exam_member(self, exam_id: int, target_member_id: int, member_id: int) -> None:
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        # 소유자는 참여자를 내보낼 수 있고, 참여자는 스스로 나갈 수 있다.
        if exam.member_id != member_id and target_member_id != member_id:
            raise ExamOwnerRequiredError()
        if target_member_id == exam.member_id:
            raise ExamOwnerRequiredError()
        if not self.exam_member_repo.exists(exam_id, target_member_id):
            raise MemberNotFoundError()
        self.exam_member_repo.delete(exam_id, target_member_id)


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    return InvitationService(
        InvitationRepository(db),
        ExamRepository(db),
        ExamMemberRepository(db),
        MemberRepository(db),
    )
