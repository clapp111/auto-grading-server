from sqlalchemy.orm import Session, selectinload

from app.enums.grade_status import GradeStatus
from app.enums.grade_method import GradeMethod
from app.models.grade import Grade


class GradeRepository:
    def __init__(self, db: Session):
        self.db = db

    def _with_relations(self):
        return [selectinload(Grade.student), selectinload(Grade.problem)]

    def get_by_id(self, grade_id: int) -> Grade | None:
        return (
            self.db.query(Grade)
            .options(*self._with_relations())
            .filter(Grade.grade_id == grade_id)
            .first()
        )

    def list_by_problem(self, problem_id: int) -> list[Grade]:
        return (
            self.db.query(Grade)
            .options(*self._with_relations())
            .filter(Grade.problem_id == problem_id)
            .order_by(Grade.student_id)
            .all()
        )

    def count_by_problem(self, problem_id: int) -> tuple[int, int]:
        base = self.db.query(Grade).filter(Grade.problem_id == problem_id)
        total = base.count()
        confirmed = base.filter(Grade.status == GradeStatus.CONFIRMED).count()
        return total, confirmed

    def create(
        self,
        problem_id: int,
        student_id: int,
        score: int,
        method: GradeMethod,
        comment: str | None = None,
        rubric_breakdown: list | None = None,
    ) -> Grade:
        grade = Grade(
            problem_id=problem_id,
            student_id=student_id,
            score=score,
            method=method,
            comment=comment,
            rubric_breakdown=rubric_breakdown,
        )
        self.db.add(grade)
        self.db.commit()
        self.db.refresh(grade)
        return grade

    def update(self, grade: Grade, **kwargs) -> Grade:
        for key, value in kwargs.items():
            setattr(grade, key, value)
        self.db.commit()
        self.db.refresh(grade)
        return grade

    def confirm_all(self, problem_id: int) -> int:
        count = (
            self.db.query(Grade)
            .filter(Grade.problem_id == problem_id, Grade.status == GradeStatus.SUGGESTED)
            .update({"status": GradeStatus.CONFIRMED}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def delete_by_problem(self, problem_id: int) -> None:
        self.db.query(Grade).filter(Grade.problem_id == problem_id).delete(synchronize_session=False)
        self.db.commit()

    def delete_all_by_student(self, student_id: int, commit: bool = True) -> None:
        (
            self.db.query(Grade)
            .filter(Grade.student_id == student_id)
            .delete(synchronize_session=False)
        )
        if commit:
            self.db.commit()
