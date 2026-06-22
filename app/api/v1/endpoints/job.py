from fastapi import APIRouter, Depends

from app.core.security import get_current_member
from app.models.member import Member
from app.schemas.common import ApiResponse
from app.schemas.job import JobResponse
from app.services.job import JobService, get_job_service


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=ApiResponse[JobResponse])
async def get_job(
    job_id: int,
    current_member: Member = Depends(get_current_member),
    service: JobService = Depends(get_job_service),
) -> ApiResponse[JobResponse]:
    return ApiResponse(data=service.get_job(job_id, current_member.member_id))
