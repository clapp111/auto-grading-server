from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import EmailAlreadyExistsError, InvalidCredentialsError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.enums.role import Role
from app.infrastructure.storage.url import get_file_url
from app.models.member import Member
from app.repositories.member import MemberRepository
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.schemas.member import MemberResponse


class AuthService:
    def __init__(self, repo: MemberRepository):
        self.repo = repo

    def signup(self, request: SignupRequest) -> TokenResponse:
        if self.repo.find_by_email(request.email):
            raise EmailAlreadyExistsError()

        member = self.repo.create(
            email=request.email,
            password=hash_password(request.password),
            affiliation=request.affiliation,
            affiliation_role=request.affiliation_role,
            role=Role.NORMAL,
        )
        return self._to_token_response(member)

    def login(self, request: LoginRequest) -> TokenResponse:
        member = self.repo.find_by_email(request.email)
        if not member or not verify_password(request.password, member.password):
            raise InvalidCredentialsError()
        return self._to_token_response(member)

    def _to_token_response(self, member: Member) -> TokenResponse:
        token = create_access_token({"sub": str(member.member_id)})
        member_response = MemberResponse.model_validate(member).model_copy(
            update={"profile_url": get_file_url(member.profile_key)}
        )
        return TokenResponse(access_token=token, member=member_response)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(MemberRepository(db))
