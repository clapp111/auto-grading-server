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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def signup(self, request: SignupRequest) -> TokenResponse:
        """신규 회원을 가입시키고 액세스 토큰을 발급한다.

        가입 회원의 계정 권한은 `Role.NORMAL`로 고정된다.

        Args:
            request: 이메일, 비밀번호, 이름, 소속 정보를 담은 가입 요청

        Returns:
            액세스 토큰과 가입한 회원 정보

        Raises:
            EmailAlreadyExistsError: 이미 사용 중인 이메일인 경우
        """
        if self.repo.find_by_email(request.email):
            raise EmailAlreadyExistsError()

        member = self.repo.create(
            email=request.email,
            password=hash_password(request.password),
            name=request.name,
            affiliation=request.affiliation,
            affiliation_role=request.affiliation_role,
            role=Role.NORMAL,
        )
        return self._to_token_response(member)

    def login(self, request: LoginRequest) -> TokenResponse:
        """이메일과 비밀번호로 로그인하고 액세스 토큰을 발급한다.

        Args:
            request: 이메일과 비밀번호를 담은 로그인 요청

        Returns:
            액세스 토큰과 회원 정보

        Raises:
            InvalidCredentialsError: 이메일이 존재하지 않거나 비밀번호가 일치하지 않는 경우
        """
        member = self.repo.find_by_email(request.email)
        if not member or not verify_password(request.password, member.password):
            raise InvalidCredentialsError()
        return self._to_token_response(member)

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _to_token_response(self, member: Member) -> TokenResponse:
        """회원 정보로 토큰 응답을 생성한다.

        저장된 프로필 key를 조회용 URL로 변환해 회원 정보에 담는다.

        Args:
            member: 토큰을 발급할 회원

        Returns:
            액세스 토큰과 회원 정보
        """
        token = create_access_token({"sub": str(member.member_id)})
        member_response = MemberResponse.model_validate(member).model_copy(
            update={"profile_url": get_file_url(member.profile_key)}
        )
        return TokenResponse(access_token=token, member=member_response)


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(MemberRepository(db))
