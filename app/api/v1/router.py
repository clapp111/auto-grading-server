from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    exam,
    problem,
    member,
    model_answer,
    rubric,
    student,
    answer_sheet,
    answer_region,
    ocr_result,
    grade,
    job,
    result,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(exam.router)
api_router.include_router(problem.router)
api_router.include_router(member.router)
api_router.include_router(model_answer.router)
api_router.include_router(rubric.router)
api_router.include_router(student.router)
api_router.include_router(answer_sheet.router)
api_router.include_router(answer_region.router)
api_router.include_router(ocr_result.router)
api_router.include_router(grade.router)
api_router.include_router(job.router)
api_router.include_router(result.router)