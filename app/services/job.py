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
        """비동기 작업(잡)을 단건 조회한다.

        잡이 속한 시험에 접근 권한이 있는 사용자만 조회할 수 있다.

        Args:
            job_id: 조회할 잡 ID
            member_id: 조회를 요청한 사용자 ID

        Returns:
            조회된 잡 정보

        Raises:
            JobNotFoundError: 잡이 없거나 접근 권한이 없는 경우
        """
        job = self.repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        exam = self.exam_repo.get_accessible(job.exam_id, member_id)
        if not exam:
            raise JobNotFoundError()
        return JobResponse.model_validate(job)


def get_job_service(db: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(db), ExamRepository(db))
