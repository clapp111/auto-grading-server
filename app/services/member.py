from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidCurrentPasswordError
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.deps import get_storage
from app.infrastructure.storage.url import get_file_url
from app.models.member import Member
from app.repositories.member import MemberRepository
from app.schemas.member import (
    MemberResponse,
    UpdatePasswordRequest,
    UpdateProfileRequest,
)
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class MemberService:
    def __init__(self, repo: MemberRepository, storage: StorageClient):
        self.repo = repo
        self.storage = storage

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def update_profile(
        self, member: Member, request: UpdateProfileRequest
    ) -> MemberResponse:
        """회원 프로필을 수정한다.

        전송된 필드만 갱신하며, `profile_url`을 `None`으로 보내면 기존 프로필 이미지를
        스토리지에서 삭제한다.

        Args:
            member: 수정할 회원
            request: 변경할 프로필 필드 (미전송 필드는 무시)

        Returns:
            수정된 회원 정보
        """
        updates = request.model_dump(exclude_unset=True)
        if "profile_url" in updates:
            new_profile_url = updates.pop("profile_url")
            if new_profile_url is None and member.profile_key:
                self.storage.delete(member.profile_key)
            updates["profile_key"] = new_profile_url
        updated = self.repo.update(member, **updates)
        return self.to_response(updated)

    def update_password(self, member: Member, request: UpdatePasswordRequest) -> None:
        """회원 비밀번호를 변경한다.

        현재 비밀번호가 일치할 때만 새 비밀번호로 변경한다.

        Args:
            member: 대상 회원
            request: 현재 비밀번호와 새 비밀번호

        Raises:
            InvalidCurrentPasswordError: 현재 비밀번호가 일치하지 않는 경우
        """
        if not verify_password(request.current_password, member.password):
            raise InvalidCurrentPasswordError()
        self.repo.update(member, password=hash_password(request.new_password))

    def get_profile_upload_url(
        self, member_id: int, request: PresignedUrlRequest
    ) -> PresignedUrlResponse:
        """프로필 이미지 업로드용 presigned URL을 발급한다.

        Args:
            member_id: 업로드 대상 회원 ID
            request: 파일명과 content type

        Returns:
            업로드 URL과 저장될 file key
        """
        file_key = self.storage.generate_key(
            f"members/{member_id}/profile", request.file_name
        )
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def to_response(self, member: Member) -> MemberResponse:
        """회원 엔티티를 응답 스키마로 변환한다.

        저장된 프로필 key를 조회용 URL로 변환해 담는다.

        Args:
            member: 변환할 회원

        Returns:
            프로필 URL이 포함된 회원 정보
        """
        return MemberResponse.model_validate(member).model_copy(
            update={"profile_url": get_file_url(member.profile_key)}
        )


def get_member_service(
    db: Session = Depends(get_db), storage: StorageClient = Depends(get_storage)
) -> MemberService:
    return MemberService(MemberRepository(db), storage)
