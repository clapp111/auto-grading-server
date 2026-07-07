from sqlalchemy.orm import Session

from app.models.student import Student


class StudentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, student_id: int) -> Student | None:
        return self.db.get(Student, student_id)

    def get_by_exam_and_no(self, exam_id: int, student_no: str) -> Student | None:
        return (
            self.db.query(Student)
            .filter(Student.exam_id == exam_id, Student.student_no == student_no)
            .first()
        )

    def create(self, exam_id: int, name: str, student_no: str) -> Student:
        student = Student(exam_id=exam_id, name=name, student_no=student_no)
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def count_by_exam(self, exam_id: int) -> int:
        return self.db.query(Student).filter(Student.exam_id == exam_id).count()

    def update(self, student: Student, **kwargs) -> Student:
        for key, value in kwargs.items():
            setattr(student, key, value)
        self.db.commit()
        self.db.refresh(student)
        return student

    def map_by_ids(self, student_ids: list[int]) -> dict[int, Student]:
        students = self.db.query(Student).filter(Student.student_id.in_(student_ids)).all()
        return {s.student_id: s for s in students}

    def delete(self, student: Student, commit: bool = True) -> None:
        self.db.delete(student)
        if commit:
            self.db.commit()
