from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import app.db.models
from app.api.v1.router import api_router
from app.core.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    UnauthorizedException,
)

app = FastAPI(
    title="AI Assisted Grading API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(EmailAlreadyExistsError)
async def email_exists_handler(request: Request, exc: EmailAlreadyExistsError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"data": None, "meta": None, "error": {"code": "EMAIL_ALREADY_EXISTS", "message": "이미 사용 중인 이메일입니다."}},
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"data": None, "meta": None, "error": {"code": "INVALID_CREDENTIALS", "message": "이메일 또는 비밀번호가 올바르지 않습니다."}},
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"data": None, "meta": None, "error": {"code": "UNAUTHORIZED", "message": "인증이 필요합니다."}},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
