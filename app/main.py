from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.db.models
from app.api.v1.router import api_router
from app.core.exceptions import (
    AlreadyExamMemberError,
    AnswerRegionNotFoundError,
    AnswerSheetNotFoundError,
    AutoGradeUnsupportedError,
    EmailAlreadyExistsError,
    ExamNotFoundError,
    ExamOwnerRequiredError,
    ExamStepConflictError,
    GradeNotFoundError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    InvitationAlreadyPendingError,
    InvitationAlreadyRespondedError,
    InvitationNotFoundError,
    JobNotFoundError,
    MemberNotFoundError,
    ModelAnswerNotFoundError,
    OcrResultNotFoundError,
    ProblemNotFoundError,
    RubricNotFoundError,
    SelfInvitationError,
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
async def email_exists_handler(
    request: Request, exc: EmailAlreadyExistsError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "EMAIL_ALREADY_EXISTS",
                "message": "이미 사용 중인 이메일입니다.",
            },
        },
    )


@app.exception_handler(InvalidCredentialsError)
async def invalid_credentials_handler(
    request: Request, exc: InvalidCredentialsError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "이메일 또는 비밀번호가 올바르지 않습니다.",
            },
        },
    )


@app.exception_handler(InvalidCurrentPasswordError)
async def invalid_current_password_handler(
    request: Request, exc: InvalidCurrentPasswordError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "INVALID_CURRENT_PASSWORD",
                "message": "현재 비밀번호가 올바르지 않습니다.",
            },
        },
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(
    request: Request, exc: UnauthorizedException
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "data": None,
            "meta": None,
            "error": {"code": "UNAUTHORIZED", "message": "인증이 필요합니다."},
        },
    )


@app.exception_handler(ExamNotFoundError)
async def exam_not_found_handler(
    request: Request, exc: ExamNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {"code": "EXAM_NOT_FOUND", "message": "시험을 찾을 수 없습니다."},
        },
    )


@app.exception_handler(JobNotFoundError)
async def job_not_found_handler(
    request: Request, exc: JobNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {"code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."},
        },
    )


@app.exception_handler(ProblemNotFoundError)
async def problem_not_found_handler(
    request: Request, exc: ProblemNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "PROBLEM_NOT_FOUND",
                "message": "문제를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(ModelAnswerNotFoundError)
async def model_answer_not_found_handler(
    request: Request, exc: ModelAnswerNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "MODEL_ANSWER_NOT_FOUND",
                "message": "모범답안을 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(RubricNotFoundError)
async def rubric_not_found_handler(
    request: Request, exc: RubricNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "RUBRIC_NOT_FOUND",
                "message": "루브릭 기준을 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(AnswerSheetNotFoundError)
async def answer_sheet_not_found_handler(
    request: Request, exc: AnswerSheetNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "ANSWER_SHEET_NOT_FOUND",
                "message": "답안지를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(AnswerRegionNotFoundError)
async def answer_region_not_found_handler(
    request: Request, exc: AnswerRegionNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "ANSWER_REGION_NOT_FOUND",
                "message": "답안 영역을 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(OcrResultNotFoundError)
async def ocr_result_not_found_handler(
    request: Request, exc: OcrResultNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "OCR_RESULT_NOT_FOUND",
                "message": "OCR 결과를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(StudentNotFoundError)
async def student_not_found_handler(
    request: Request, exc: StudentNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "STUDENT_NOT_FOUND",
                "message": "학생을 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(GradeNotFoundError)
async def grade_not_found_handler(
    request: Request, exc: GradeNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "GRADE_NOT_FOUND",
                "message": "채점 결과를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(ExamStepConflictError)
async def exam_step_conflict_handler(
    request: Request, exc: ExamStepConflictError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "EXAM_STEP_CONFLICT",
                "message": "시험의 현재 단계가 요청한 단계와 일치하지 않습니다.",
            },
        },
    )


@app.exception_handler(AutoGradeUnsupportedError)
async def auto_grade_unsupported_handler(
    request: Request, exc: AutoGradeUnsupportedError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "AUTO_GRADE_UNSUPPORTED",
                "message": "객관식/단답형은 자동 채점을 지원하지 않습니다. 수작업으로 채점해주세요.",
            },
        },
    )


@app.exception_handler(MemberNotFoundError)
async def member_not_found_handler(
    request: Request, exc: MemberNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "MEMBER_NOT_FOUND",
                "message": "해당 이메일의 사용자를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(InvitationNotFoundError)
async def invitation_not_found_handler(
    request: Request, exc: InvitationNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "INVITATION_NOT_FOUND",
                "message": "초대를 찾을 수 없습니다.",
            },
        },
    )


@app.exception_handler(SelfInvitationError)
async def self_invitation_handler(
    request: Request, exc: SelfInvitationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "SELF_INVITATION",
                "message": "자기 자신은 초대할 수 없습니다.",
            },
        },
    )


@app.exception_handler(AlreadyExamMemberError)
async def already_exam_member_handler(
    request: Request, exc: AlreadyExamMemberError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "ALREADY_EXAM_MEMBER",
                "message": "이미 시험에 참여 중인 사용자입니다.",
            },
        },
    )


@app.exception_handler(InvitationAlreadyRespondedError)
async def invitation_already_responded_handler(
    request: Request, exc: InvitationAlreadyRespondedError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "INVITATION_ALREADY_RESPONDED",
                "message": "이미 처리된 초대입니다.",
            },
        },
    )


@app.exception_handler(InvitationAlreadyPendingError)
async def invitation_already_pending_handler(
    request: Request, exc: InvitationAlreadyPendingError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "INVITATION_ALREADY_PENDING",
                "message": "이미 대기 중인 초대가 있습니다.",
            },
        },
    )


@app.exception_handler(ExamOwnerRequiredError)
async def exam_owner_required_handler(
    request: Request, exc: ExamOwnerRequiredError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "data": None,
            "meta": None,
            "error": {
                "code": "EXAM_OWNER_REQUIRED",
                "message": "시험 소유자만 수행할 수 있습니다.",
            },
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
