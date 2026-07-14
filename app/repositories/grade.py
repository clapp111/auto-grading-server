from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.enums.grade_status import GradeStatus
from app.enums.grade_method import GradeMethod
from app.models.grade import Grade
from app.models.student import Student


class GradeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, grade_id: int) -> Grade | None:
        return self.db.get(Grade, grade_id)

    def list_by_problem(self, problem_id: int) -> list[Grade]:
        return (
            self.db.query(Grade)
            .join(Student, Grade.student_id == Student.student_id)
            .filter(Grade.problem_id == problem_id)
            .order_by(Student.student_no)
            .all()
        )

    def count_by_problem(self, problem_id: int) -> tuple[int, int]:
        base = self.db.query(Grade).filter(Grade.problem_id == problem_id)
        total = base.count()
        confirmed = base.filter(Grade.status == GradeStatus.CONFIRMED).count()
        return total, confirmed

    def count_by_problems(self, problem_ids: list[int]) -> dict[int, tuple[int, int]]:
        if not problem_ids:
            return {}
        rows = (
            self.db.query(
                Grade.problem_id,
                func.count(Grade.grade_id),
                func.count(case((Grade.status == GradeStatus.CONFIRMED, Grade.grade_id))),
            )
            .filter(Grade.problem_id.in_(problem_ids))
            .group_by(Grade.problem_id)
            .all()
        )
        return {problem_id: (total, confirmed) for problem_id, total, confirmed in rows}

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

    def get_by_problem_and_student(self, problem_id: int, student_id: int) -> Grade | None:
        return (
            self.db.query(Grade)
            .filter(Grade.problem_id == problem_id, Grade.student_id == student_id)
            .first()
        )

    def delete_by_problem(self, problem_id: int) -> None:
        self.db.query(Grade).filter(Grade.problem_id == problem_id).delete(synchronize_session=False)
        self.db.commit()
