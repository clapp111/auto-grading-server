from fastapi import APIRouter, Depends

from app.schemas.common import ApiResponse
from app.schemas.job import JobResponse
from app.services.job_service import JobService, get_job_service


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
async def get_job(
    job_id: int,
    service: JobService = Depends(get_job_service),
) -> ApiResponse[JobResponse]:
    return ApiResponse(data=service.get_job(job_id))
