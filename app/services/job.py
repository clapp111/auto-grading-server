from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import JobNotFoundError
from app.db.session import get_db
from app.repositories.exam import ExamRepository
from app.repositories.job import JobRepository
from app.schemas.job import JobResponse


class JobService:
    def __init__(self, repo: JobRepository, exam_repo: ExamRepository):
        self.repo = repo
        self.exam_repo = exam_repo

    def get_job(self, job_id: int, member_id: int) -> JobResponse:
        job = self.repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        exam = self.exam_repo.get_by_id(job.exam_id)
        if not exam or exam.member_id != member_id:
            raise JobNotFoundError()
        return JobResponse.model_validate(job)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(db), ExamRepository(db))
