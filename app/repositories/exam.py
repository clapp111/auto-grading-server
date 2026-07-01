from sqlalchemy import delete, func, select, update as sa_update
from sqlalchemy.orm import Session

from app.models.answer_region import AnswerRegion
from app.models.answer_sheet import AnswerSheet
from app.models.exam import Exam
from app.models.grade import Grade
from app.models.job import Job
from app.models.model_answer import ModelAnswer
from app.models.ocr_result import OCRResult
from app.models.problem import Problem
from app.models.rubric import Rubric
from app.models.student import Student


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
        step: int | None,
    ) -> list[Exam]:
        q = self.db.query(Exam).filter(Exam.member_id == member_id)
        if search:
            q = q.filter(Exam.name.ilike(f"%{search}%"))
        if step is not None:
            q = q.filter(Exam.step == step)
        if cursor_id is not None:
            q = q.filter(Exam.exam_id < cursor_id)
        return q.order_by(Exam.exam_id.desc()).limit(size + 1).all()

    def count_by_step(self, member_id: int) -> dict[str, int]:
        rows = (
            self.db.query(Exam.step, func.count(Exam.exam_id))
            .filter(Exam.member_id == member_id)
            .group_by(Exam.step)
            .all()
        )
        counts = {row[0]: row[1] for row in rows}
        return {
            "draft": counts.get(0, 0),
            "in_progress": sum(counts.get(s, 0) for s in range(1, 7)),
            "done": counts.get(7, 0),
        }

    def create(self, member_id: int, name: str, description: str | None) -> Exam:
        exam = Exam(member_id=member_id, name=name, description=description)
        self.db.add(exam)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def touch(self, exam_id: int) -> None:
        self.db.execute(sa_update(Exam).where(Exam.exam_id == exam_id).values(updated_at=func.now()))
        self.db.commit()

    def update(self, exam: Exam, **kwargs) -> Exam:
        for key, value in kwargs.items():
            setattr(exam, key, value)
        self.db.commit()
        self.db.refresh(exam)
        return exam

    def get_answer_sheet_file_keys(self, exam_id: int) -> list[str]:
        return list(
            self.db.execute(
                select(AnswerSheet.file_key).where(AnswerSheet.exam_id == exam_id)
            ).scalars().all()
        )

    def delete_cascade(self, exam_id: int) -> None:
        problem_ids = select(Problem.problem_id).where(Problem.exam_id == exam_id)
        sheet_ids = select(AnswerSheet.answer_sheet_id).where(AnswerSheet.exam_id == exam_id)
        region_ids = select(AnswerRegion.answer_region_id).where(AnswerRegion.answer_sheet_id.in_(sheet_ids))

        self.db.execute(delete(Grade).where(Grade.problem_id.in_(problem_ids)))
        self.db.execute(delete(OCRResult).where(OCRResult.answer_region_id.in_(region_ids)))
        self.db.execute(delete(AnswerRegion).where(AnswerRegion.answer_sheet_id.in_(sheet_ids)))
        self.db.execute(delete(AnswerSheet).where(AnswerSheet.exam_id == exam_id))
        self.db.execute(delete(Rubric).where(Rubric.problem_id.in_(problem_ids)))
        self.db.execute(delete(ModelAnswer).where(ModelAnswer.problem_id.in_(problem_ids)))
        self.db.execute(delete(Job).where(Job.exam_id == exam_id))
        self.db.execute(delete(Problem).where(Problem.exam_id == exam_id))
        self.db.execute(delete(Student).where(Student.exam_id == exam_id))
        self.db.execute(delete(Exam).where(Exam.exam_id == exam_id))
        self.db.commit()
