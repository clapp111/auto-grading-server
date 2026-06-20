from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/exams/{exam_id}/results", tags=["results"])


@router.get("/summary")
async def get_result_summary(exam_id: str):
    pass


@router.get("/students")
async def get_student_results(exam_id: str):
    pass


@router.get("/export.csv", response_class=StreamingResponse)
async def export_results_csv(exam_id: str):
    pass
