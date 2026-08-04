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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def create_invitation(
        self, exam_id: int, member_id: int, request: InvitationCreateRequest
    ) -> ExamInvitationResponse:
        """시험에 참여자를 초대한다.

        소유자만 초대할 수 있으며, 이미 참여 중이거나 대기 중인 초대가 있으면 거부한다.

        Args:
            exam_id: 초대를 생성할 시험 ID
            member_id: 초대를 요청한 사용자(소유자) ID
            request: 초대할 대상의 이메일을 담은 요청

        Returns:
            생성된 초대 정보

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ExamOwnerRequiredError: 시험 소유자가 아닌 경우
            MemberNotFoundError: 초대 대상 이메일의 사용자가 없는 경우
            SelfInvitationError: 자기 자신을 초대한 경우
            AlreadyExamMemberError: 이미 참여 중인 사용자인 경우
            InvitationAlreadyPendingError: 이미 대기 중인 초대가 있는 경우
        """
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

    def list_exam_invitations(
        self, exam_id: int, member_id: int, status: InvitationStatus | None
    ) -> list[ExamInvitationResponse]:
        """시험에 보낸 초대 목록을 조회한다.

        소유자만 조회할 수 있다.

        Args:
            exam_id: 초대를 조회할 시험 ID
            member_id: 조회를 요청한 사용자(소유자) ID
            status: 특정 상태로 필터링할 값

        Returns:
            초대받은 사람 정보가 포함된 초대 목록

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ExamOwnerRequiredError: 시험 소유자가 아닌 경우
        """
        self._get_owned_exam_or_raise(exam_id, member_id)
        rows = self.repo.list_by_exam_with_invitee(exam_id, status)
        return [
            self._to_exam_invitation_response(inv, invitee) for inv, invitee in rows
        ]

    def cancel_invitation(self, invitation_id: int, member_id: int) -> None:
        """소유자가 보낸 대기 중인 초대를 취소한다.

        Args:
            invitation_id: 취소할 초대 ID
            member_id: 취소를 요청한 사용자(소유자) ID

        Raises:
            InvitationNotFoundError: 초대가 없거나 해당 시험의 소유자가 아닌 경우
            InvitationAlreadyRespondedError: 이미 처리(수락/거절/취소)된 초대인 경우
        """
        invitation = self.repo.get_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFoundError()
        exam = self.exam_repo.get_owned(invitation.exam_id, member_id)
        if not exam:
            raise InvitationNotFoundError()
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()
        self.repo.update_status(invitation, InvitationStatus.CANCELED)

    def list_received_invitations(
        self, member_id: int, status: InvitationStatus | None
    ) -> list[InvitationResponse]:
        """사용자가 받은 초대 목록을 조회한다.

        Args:
            member_id: 초대를 받은 사용자 ID
            status: 특정 상태로 필터링할 값

        Returns:
            시험·초대자 정보가 포함된 초대 목록
        """
        rows = self.repo.list_received_with_context(member_id, status)
        return [
            self._to_received_response(inv, exam, inviter)
            for inv, exam, inviter in rows
        ]

    def accept_invitation(self, invitation_id: int, member_id: int) -> None:
        """받은 초대를 수락하고 시험 참여자로 등록한다.

        Args:
            invitation_id: 수락할 초대 ID
            member_id: 초대를 받은 사용자 ID

        Raises:
            InvitationNotFoundError: 초대가 없거나 본인이 받은 초대가 아닌 경우
            InvitationAlreadyRespondedError: 이미 처리된 초대인 경우
        """
        invitation = self._get_received_invitation_or_raise(invitation_id, member_id)
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()

        if not self.exam_member_repo.exists(invitation.exam_id, member_id):
            self.exam_member_repo.create(invitation.exam_id, member_id)
        self.repo.update_status(invitation, InvitationStatus.ACCEPTED)

    def decline_invitation(self, invitation_id: int, member_id: int) -> None:
        """받은 초대를 거절한다.

        Args:
            invitation_id: 거절할 초대 ID
            member_id: 초대를 받은 사용자 ID

        Raises:
            InvitationNotFoundError: 초대가 없거나 본인이 받은 초대가 아닌 경우
            InvitationAlreadyRespondedError: 이미 처리된 초대인 경우
        """
        invitation = self._get_received_invitation_or_raise(invitation_id, member_id)
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationAlreadyRespondedError()
        self.repo.update_status(invitation, InvitationStatus.DECLINED)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _get_owned_exam_or_raise(self, exam_id: int, member_id: int) -> Exam:
        """소유한 시험을 조회하고, 아니면 예외를 던진다.

        참여자에게는 소유자 전용 동작임을 알려주고(`ExamOwnerRequiredError`),
        무관한 사용자에게는 시험 존재 자체를 숨긴다(`ExamNotFoundError`).

        Args:
            exam_id: 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            소유 중인 시험

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ExamOwnerRequiredError: 참여자이지만 소유자가 아닌 경우
        """
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        if exam.member_id != member_id:
            raise ExamOwnerRequiredError()
        return exam

    def _get_received_invitation_or_raise(
        self, invitation_id: int, member_id: int
    ) -> Invitation:
        """본인이 받은 초대를 조회하고, 아니면 예외를 던진다.

        Args:
            invitation_id: 조회할 초대 ID
            member_id: 요청한 사용자 ID

        Returns:
            본인이 받은 초대

        Raises:
            InvitationNotFoundError: 초대가 없거나 본인이 받은 초대가 아닌 경우
        """
        invitation = self.repo.get_by_id(invitation_id)
        if not invitation or invitation.invitee_member_id != member_id:
            raise InvitationNotFoundError()
        return invitation

    @staticmethod
    def _to_received_response(
        invitation: Invitation, exam: Exam, inviter: Member
    ) -> InvitationResponse:
        """받은 초대를 수신자 관점 응답 스키마로 변환한다.

        Args:
            invitation: 변환할 초대
            exam: 초대가 속한 시험
            inviter: 초대를 보낸 사용자

        Returns:
            시험·초대자 정보가 포함된 초대 응답
        """
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
    def _to_exam_invitation_response(
        invitation: Invitation, invitee: Member
    ) -> ExamInvitationResponse:
        """보낸 초대를 소유자 관점 응답 스키마로 변환한다.

        Args:
            invitation: 변환할 초대
            invitee: 초대받은 사용자

        Returns:
            초대받은 사람 정보가 포함된 초대 응답
        """
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


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    return InvitationService(
        InvitationRepository(db),
        ExamRepository(db),
        ExamMemberRepository(db),
        MemberRepository(db),
    )
