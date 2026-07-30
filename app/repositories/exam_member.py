from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.exam_member import ExamMember
from app.models.member import Member


class ExamMemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def exists(self, exam_id: int, member_id: int) -> bool:
        return (
            self.db.query(ExamMember.exam_member_id)
            .filter(ExamMember.exam_id == exam_id, ExamMember.member_id == member_id)
            .first()
            is not None
        )

    def list_with_member_by_exam(self, exam_id: int) -> list[tuple[ExamMember, Member]]:
        return (
            self.db.query(ExamMember, Member)
            .join(Member, ExamMember.member_id == Member.member_id)
            .filter(ExamMember.exam_id == exam_id)
            .order_by(ExamMember.exam_member_id)
            .all()
        )

    def create(self, exam_id: int, member_id: int) -> ExamMember:
        exam_member = ExamMember(exam_id=exam_id, member_id=member_id)
        self.db.add(exam_member)
        self.db.commit()
        self.db.refresh(exam_member)
        return exam_member

    def delete(self, exam_id: int, member_id: int) -> None:
        self.db.execute(
            delete(ExamMember).where(
                ExamMember.exam_id == exam_id,
                ExamMember.member_id == member_id,
            )
        )
        self.db.commit()
