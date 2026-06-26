from sqlalchemy.orm import Session, selectinload

from app.enums.ocr_status import OCRStatus
from app.models.answer_region import AnswerRegion
from app.models.answer_sheet import AnswerSheet
from app.models.ocr_result import OCRResult


def _with_relations():
    return selectinload(OCRResult.answer_region).options(
        selectinload(AnswerRegion.problem),
        selectinload(AnswerRegion.answer_sheet),
    )


class OcrResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, ocr_result_id: int) -> OCRResult | None:
        return (
            self.db.query(OCRResult)
            .options(_with_relations())
            .filter(OCRResult.ocr_result_id == ocr_result_id)
            .first()
        )

    def list_by_student(self, student_id: int) -> list[OCRResult]:
        return (
            self.db.query(OCRResult)
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .join(AnswerSheet, AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id)
            .options(_with_relations())
            .filter(AnswerSheet.student_id == student_id)
            .order_by(AnswerRegion.problem_id)
            .all()
        )

    def count_by_answer_sheet(self, answer_sheet_id: int) -> tuple[int, int]:
        base = (
            self.db.query(OCRResult)
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .filter(AnswerRegion.answer_sheet_id == answer_sheet_id)
        )
        total = base.count()
        confirmed = base.filter(OCRResult.status == OCRStatus.REVIEWED).count()
        return total, confirmed

    def map_by_problem(self, problem_id: int) -> dict[int, OCRResult]:
        rows = (
            self.db.query(OCRResult, AnswerSheet.student_id)
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .join(AnswerSheet, AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id)
            .filter(AnswerRegion.problem_id == problem_id)
            .all()
        )
        return {student_id: ocr_result for ocr_result, student_id in rows}

    def update(self, ocr_result: OCRResult, **kwargs) -> OCRResult:
        for key, value in kwargs.items():
            setattr(ocr_result, key, value)
        self.db.commit()
        self.db.refresh(ocr_result)
        return ocr_result
