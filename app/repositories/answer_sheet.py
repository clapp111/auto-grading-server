from sqlalchemy.orm import Session

from app.enums.sheet_status import SheetStatus
from app.models.answer_sheet import AnswerSheet


class AnswerSheetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, answer_sheet_id: int) -> AnswerSheet | None:
        return self.db.get(AnswerSheet, answer_sheet_id)

    def list_by_exam(self, exam_id: int) -> list[AnswerSheet]:
        return self.db.query(AnswerSheet).filter(AnswerSheet.exam_id == exam_id).all()

    def list_unmatched_by_exam(self, exam_id: int) -> list[AnswerSheet]:
        return (
            self.db.query(AnswerSheet)
            .filter(AnswerSheet.exam_id == exam_id, AnswerSheet.status == SheetStatus.UNMATCHED)
            .all()
        )

    def create(self, exam_id: int, file_key: str) -> AnswerSheet:
        sheet = AnswerSheet(exam_id=exam_id, file_key=file_key)
        self.db.add(sheet)
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

    def update(self, sheet: AnswerSheet, **kwargs) -> AnswerSheet:
        for key, value in kwargs.items():
            setattr(sheet, key, value)
        self.db.commit()
        self.db.refresh(sheet)
        return sheet

    def delete(self, sheet: AnswerSheet) -> None:
        self.db.delete(sheet)
        self.db.commit()
