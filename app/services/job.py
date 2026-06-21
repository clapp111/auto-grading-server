from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import JobNotFoundError
from app.db.session import get_db
from app.repositories.job import JobRepository
from app.schemas.job import JobResponse


class JobService:
    def __init__(self, repo: JobRepository):
        self.repo = repo

    def get_job(self, job_id: int) -> JobResponse:
        job = self.repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        return JobResponse.model_validate(job)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(db))
