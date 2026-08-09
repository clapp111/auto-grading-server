from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

ExceptionHandler = Callable[[Request, Exception], JSONResponse]
ExceptionConfig = tuple[type[Exception], int, str, str]

EXCEPTION_CONFIGS: tuple[ExceptionConfig, ...] = (
    (
        EmailAlreadyExistsError,
        409,
        "EMAIL_ALREADY_EXISTS",
        "이미 사용 중인 이메일입니다.",
    ),
    (
        InvalidCredentialsError,
        401,
        "INVALID_CREDENTIALS",
        "이메일 또는 비밀번호가 올바르지 않습니다.",
    ),
    (
        InvalidCurrentPasswordError,
        400,
        "INVALID_CURRENT_PASSWORD",
        "현재 비밀번호가 올바르지 않습니다.",
    ),
    (UnauthorizedException, 401, "UNAUTHORIZED", "인증이 필요합니다."),
    (ExamNotFoundError, 404, "EXAM_NOT_FOUND", "시험을 찾을 수 없습니다."),
    (JobNotFoundError, 404, "JOB_NOT_FOUND", "작업을 찾을 수 없습니다."),
    (ProblemNotFoundError, 404, "PROBLEM_NOT_FOUND", "문제를 찾을 수 없습니다."),
    (
        ModelAnswerNotFoundError,
        404,
        "MODEL_ANSWER_NOT_FOUND",
        "모범 답안을 찾을 수 없습니다.",
    ),
    (RubricNotFoundError, 404, "RUBRIC_NOT_FOUND", "루브릭을 찾을 수 없습니다."),
    (
        AnswerSheetNotFoundError,
        404,
        "ANSWER_SHEET_NOT_FOUND",
        "답안지를 찾을 수 없습니다.",
    ),
    (
        AnswerRegionNotFoundError,
        404,
        "ANSWER_REGION_NOT_FOUND",
        "답안 영역을 찾을 수 없습니다.",
    ),
    (
        OcrResultNotFoundError,
        404,
        "OCR_RESULT_NOT_FOUND",
        "OCR 결과를 찾을 수 없습니다.",
    ),
    (StudentNotFoundError, 404, "STUDENT_NOT_FOUND", "학생을 찾을 수 없습니다."),
    (GradeNotFoundError, 404, "GRADE_NOT_FOUND", "채점 결과를 찾을 수 없습니다."),
    (
        ExamStepConflictError,
        409,
        "EXAM_STEP_CONFLICT",
        "시험의 현재 단계가 요청한 단계와 일치하지 않습니다.",
    ),
    (
        AutoGradeUnsupportedError,
        409,
        "AUTO_GRADE_UNSUPPORTED",
        "자동 채점을 지원하지 않습니다.",
    ),
    (MemberNotFoundError, 404, "MEMBER_NOT_FOUND", "회원을 찾을 수 없습니다."),
    (
        InvitationNotFoundError,
        404,
        "INVITATION_NOT_FOUND",
        "초대 정보를 찾을 수 없습니다.",
    ),
    (SelfInvitationError, 400, "SELF_INVITATION", "자기 자신을 초대할 수 없습니다."),
    (
        AlreadyExamMemberError,
        409,
        "ALREADY_EXAM_MEMBER",
        "이미 시험에 참여 중인 사용자입니다.",
    ),
    (
        InvitationAlreadyRespondedError,
        409,
        "INVITATION_ALREADY_RESPONDED",
        "이미 처리된 초대입니다.",
    ),
    (
        InvitationAlreadyPendingError,
        409,
        "INVITATION_ALREADY_PENDING",
        "이미 대기 중인 초대가 있습니다.",
    ),
    (
        ExamOwnerRequiredError,
        403,
        "EXAM_OWNER_REQUIRED",
        "시험 소유자만 수행할 수 있습니다.",
    ),
)


def create_exception_handler(
    status_code: int, error_code: str, message: str
) -> ExceptionHandler:
    async def handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "data": None,
                "meta": None,
                "error": {"code": error_code, "message": message},
            },
        )

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    for exception, status_code, error_code, message in EXCEPTION_CONFIGS:
        app.add_exception_handler(
            exception,
            create_exception_handler(status_code, error_code, message),
        )
