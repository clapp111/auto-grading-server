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
from app.schemas.member import MemberResponse, UpdatePasswordRequest, UpdateProfileRequest
from app.schemas.s3 import PresignedUrlRequest, PresignedUrlResponse


class MemberService:
    def __init__(self, repo: MemberRepository, storage: StorageClient):
        self.repo = repo
        self.storage = storage

    def to_response(self, member: Member) -> MemberResponse:
        return MemberResponse.model_validate(member).model_copy(
            update={"profile_url": get_file_url(member.profile_key)}
        )

    def update_profile(self, member: Member, request: UpdateProfileRequest) -> MemberResponse:
        updates = request.model_dump(exclude_unset=True)
        if "profile_url" in updates:
            new_profile_url = updates.pop("profile_url")
            if new_profile_url is None and member.profile_key:
                self.storage.delete(member.profile_key)
            updates["profile_key"] = new_profile_url
        updated = self.repo.update(member, **updates)
        return self.to_response(updated)

    def update_password(self, member: Member, request: UpdatePasswordRequest) -> None:
        if not verify_password(request.current_password, member.password):
            raise InvalidCurrentPasswordError()
        self.repo.update(member, password=hash_password(request.new_password))

    def get_profile_upload_url(self, member_id: int, request: PresignedUrlRequest) -> PresignedUrlResponse:
        file_key = self.storage.generate_key(f"members/{member_id}/profile", request.file_name)
        upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
        return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)


def get_member_service(db: Session = Depends(get_db), storage: StorageClient = Depends(get_storage)) -> MemberService:
    return MemberService(MemberRepository(db), storage)
