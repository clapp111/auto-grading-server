from sqlalchemy.orm import Session, selectinload

from app.models.grade import Grade
from app.models.problem import Problem
from app.models.student import Student


class ResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_students_by_exam(self, exam_id: int) -> list[Student]:
        return (
            self.db.query(Student)
            .filter(Student.exam_id == exam_id)
            .order_by(Student.student_no)
            .all()
        )

    def map_grades_by_exam(self, exam_id: int) -> dict[tuple[int, int], Grade]:
        """(problem_id, student_id) → Grade 매핑. 성적 격자·통계 모두 이 결과 재사용."""
        grades = (
            self.db.query(Grade)
            .join(Problem, Grade.problem_id == Problem.problem_id)
            .filter(Problem.exam_id == exam_id)
            .all()
        )
        return {(g.problem_id, g.student_id): g for g in grades}

    def list_grades_by_student_exam(self, student_id: int, exam_id: int) -> list[Grade]:
        """특정 학생의 시험 전체 채점 결과 (problem 순서). student/problem 관계 포함."""
        return (
            self.db.query(Grade)
            .join(Problem, Grade.problem_id == Problem.problem_id)
            .options(selectinload(Grade.student), selectinload(Grade.problem))
            .filter(Grade.student_id == student_id, Problem.exam_id == exam_id)
            .order_by(Problem.problem_id)
            .all()
        )
