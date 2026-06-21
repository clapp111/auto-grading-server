from sqlalchemy.orm import Session

from app.models.member import Member


class MemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_email(self, email: str) -> Member | None:
        return self.db.query(Member).filter(Member.email == email).first()

    def find_by_id(self, member_id: int) -> Member | None:
        return self.db.get(Member, member_id)

    def create(self, **kwargs) -> Member:
        member = Member(**kwargs)
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member
