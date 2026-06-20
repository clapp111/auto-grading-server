from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    exams,
    problems,
    members,
    model_answers,
    rubrics,
    students,
    answer_sheets,
    answer_regions,
    ocr_results,
    grades,
    jobs,
    results,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(exams.router)
api_router.include_router(problems.router)
api_router.include_router(members.router)
api_router.include_router(model_answers.router)
api_router.include_router(rubrics.router)
api_router.include_router(students.router)
api_router.include_router(answer_sheets.router)
api_router.include_router(answer_regions.router)
api_router.include_router(ocr_results.router)
api_router.include_router(grades.router)
api_router.include_router(jobs.router)
api_router.include_router(results.router)