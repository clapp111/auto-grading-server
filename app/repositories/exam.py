from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums.exam_status import ExamStatus
from app.models.exam import Exam


class ExamRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, exam_id: int) -> Exam | None:
        return self.db.get(Exam, exam_id)

    def list_by_member(
        self,
        member_id: int,
        cursor_id: int | None,
        size: int,
        search: str | None,
        status: ExamStatus | None,
    ) -> list[Exam]:
        q = self.db.query(Exam).filter(Exam.member_id == member_id)
        if search:
            q = q.filter(Exam.name.ilike(f"%{search}%"))
        if status:
            q = q.filter(Exam.status == status)
        if cursor_id is not None:
            q = q.filter(Exam.exam_id < cursor_id)
        return q.order_by(Exam.exam_id.desc()).limit(size + 1).all()

    def count_by_status(self, member_id: int) -> dict[str, int]:
        rows = (
            self.db.query(Exam.status, func.count(Exam.exam_id))
            .filter(Exam.member_id == member_id)
            .group_by(Exam.status)
            .all()
        )
        counts = {row[0]: row[1] for row in rows}
        in_progress_statuses = {ExamStatus.SETUP, ExamStatus.OCR, ExamStatus.GRADING}
        return {
            "draft": counts.get(ExamStatus.DRAFT, 0),
            "in_progress": sum(counts.get(s, 0) for s in in_progress_statuses),
            "done": counts.get(ExamStatus.DONE, 0),
        }

    def create(self, member_id: int, name: str, description: str | None) -> Exam:
        exam = Exam(member_id=member_id, name=name, description=description)
        self.db.add(exam)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def update(self, exam: Exam, **kwargs) -> Exam:
        for key, value in kwargs.items():
            setattr(exam, key, value)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def delete(self, exam: Exam) -> None:
        self.db.delete(exam)
        self.db.commit()
