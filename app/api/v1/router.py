from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    exam,
    problem,
    member,
    model_answer,
    rubric,
    answer_sheet,
    answer_region,
    ocr_result,
    grade,
    job,
    result,
    invitation,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(exam.router)
api_router.include_router(problem.router)
api_router.include_router(member.router)
api_router.include_router(model_answer.router)
api_router.include_router(rubric.router)
api_router.include_router(answer_sheet.router)
api_router.include_router(answer_region.router)
api_router.include_router(ocr_result.router)
api_router.include_router(grade.router)
api_router.include_router(job.router)
api_router.include_router(result.router)
api_router.include_router(invitation.router)
api_router.include_router(invitation.exam_router)