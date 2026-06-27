from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.db.models
from app.api.v1.router import api_router
from app.core.exceptions import (
    AnswerRegionNotFoundError,
    AnswerSheetNotFoundError,
    EmailAlreadyExistsError,
    ExamNotFoundError,
    GradeNotFoundError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    JobNotFoundError,
    ModelAnswerNotFoundError,
    OcrResultNotFoundError,
    ProblemNotFoundError,
    RubricNotFoundError,
    StudentNotFoundError,
    UnauthorizedException,
)

app = FastAPI(
    title="AI Assisted Grading API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.exception_handler(InvalidCurrentPasswordError)
async def invalid_current_password_handler(request: Request, exc: InvalidCurrentPasswordError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"data": None, "meta": None, "error": {"code": "INVALID_CURRENT_PASSWORD", "message": "현재 비밀번호가 올바르지 않습니다."}},
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(request: Request, exc: UnauthorizedException) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"data": None, "meta": None, "error": {"code": "UNAUTHORIZED", "message": "인증이 필요합니다."}},
    )


@app.exception_handler(ExamNotFoundError)
async def exam_not_found_handler(request: Request, exc: ExamNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "EXAM_NOT_FOUND", "message": "시험을 찾을 수 없습니다."}},
    )


@app.exception_handler(JobNotFoundError)
async def job_not_found_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."}},
    )


@app.exception_handler(ProblemNotFoundError)
async def problem_not_found_handler(request: Request, exc: ProblemNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "PROBLEM_NOT_FOUND", "message": "문제를 찾을 수 없습니다."}},
    )


@app.exception_handler(ModelAnswerNotFoundError)
async def model_answer_not_found_handler(request: Request, exc: ModelAnswerNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "MODEL_ANSWER_NOT_FOUND", "message": "모범답안을 찾을 수 없습니다."}},
    )


@app.exception_handler(RubricNotFoundError)
async def rubric_not_found_handler(request: Request, exc: RubricNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "RUBRIC_NOT_FOUND", "message": "루브릭 기준을 찾을 수 없습니다."}},
    )


@app.exception_handler(AnswerSheetNotFoundError)
async def answer_sheet_not_found_handler(request: Request, exc: AnswerSheetNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "ANSWER_SHEET_NOT_FOUND", "message": "답안지를 찾을 수 없습니다."}},
    )


@app.exception_handler(AnswerRegionNotFoundError)
async def answer_region_not_found_handler(request: Request, exc: AnswerRegionNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "ANSWER_REGION_NOT_FOUND", "message": "답안 영역을 찾을 수 없습니다."}},
    )


@app.exception_handler(OcrResultNotFoundError)
async def ocr_result_not_found_handler(request: Request, exc: OcrResultNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "OCR_RESULT_NOT_FOUND", "message": "OCR 결과를 찾을 수 없습니다."}},
    )


@app.exception_handler(StudentNotFoundError)
async def student_not_found_handler(request: Request, exc: StudentNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "STUDENT_NOT_FOUND", "message": "학생을 찾을 수 없습니다."}},
    )


@app.exception_handler(GradeNotFoundError)
async def grade_not_found_handler(request: Request, exc: GradeNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"data": None, "meta": None, "error": {"code": "GRADE_NOT_FOUND", "message": "채점 결과를 찾을 수 없습니다."}},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
