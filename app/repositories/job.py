from sqlalchemy.orm import Session

from app.enums.job_status import JobStatus
from app.enums.job_type import JobType
from app.models.job import Job


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def find_by_idempotency_key(self, key: str) -> Job | None:
        return self.db.query(Job).filter(Job.idempotency_key == key).first()

    def create(
        self,
        exam_id: int,
        type: JobType,
        requested_by_member_id: int,
        problem_id: int | None = None,
        input_json: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Job:
        job = Job(
            exam_id=exam_id,
            type=type,
            requested_by_member_id=requested_by_member_id,
            problem_id=problem_id,
            status=JobStatus.PENDING,
            input_json=input_json,
            idempotency_key=idempotency_key,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
