from fastapi import APIRouter, Depends

from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=ApiResponse[TokenResponse])
async def signup(
    request: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[TokenResponse]:
    return ApiResponse(data=service.signup(request))


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[TokenResponse]:
    return ApiResponse(data=service.login(request))
