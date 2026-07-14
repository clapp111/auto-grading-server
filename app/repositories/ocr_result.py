from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.enums.layout_mode import LayoutMode
from app.enums.ocr_status import OCRStatus
from app.enums.problem_type import ProblemType
from app.models.answer_region import AnswerRegion
from app.models.answer_sheet import AnswerSheet
from app.models.ocr_result import OCRResult
from app.models.problem import Problem

_OCR_EXCLUDED_TYPES = (ProblemType.MULTIPLE_CHOICE, ProblemType.SHORT_ANSWER)


class OcrResultRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, ocr_result_id: int) -> OCRResult | None:
        return self.db.get(OCRResult, ocr_result_id)

    def list_by_student(self, student_id: int, layout_mode: LayoutMode | None = None) -> list[tuple[OCRResult, AnswerRegion]]:
        query = (
            self.db.query(OCRResult, AnswerRegion)
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .join(AnswerSheet, AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id)
            .join(Problem, AnswerRegion.problem_id == Problem.problem_id)
            .filter(
                AnswerSheet.student_id == student_id,
                Problem.type.notin_(_OCR_EXCLUDED_TYPES),
            )
            .order_by(AnswerRegion.problem_id)
        )
        if layout_mode is not None:
            query = query.filter(AnswerRegion.layout_mode == layout_mode)
        return query.all()

    def count_by_answer_sheet(self, answer_sheet_id: int, layout_mode: LayoutMode | None = None) -> tuple[int, int]:
        base = (
            self.db.query(OCRResult)
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .filter(AnswerRegion.answer_sheet_id == answer_sheet_id)
        )
        if layout_mode is not None:
            base = base.filter(AnswerRegion.layout_mode == layout_mode)
        total = base.count()
        confirmed = base.filter(OCRResult.status == OCRStatus.REVIEWED).count()
        return total, confirmed

    def count_by_answer_sheets(
        self,
        answer_sheet_ids: list[int],
        layout_mode: LayoutMode | None = None,
    ) -> dict[int, tuple[int, int]]:
        if not answer_sheet_ids:
            return {}
        query = (
            self.db.query(
                AnswerRegion.answer_sheet_id,
                func.count(OCRResult.ocr_result_id),
                func.count(case((OCRResult.status == OCRStatus.REVIEWED, OCRResult.ocr_result_id))),
            )
            .join(AnswerRegion, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .filter(AnswerRegion.answer_sheet_id.in_(answer_sheet_ids))
        )
        if layout_mode is not None:
            query = query.filter(AnswerRegion.layout_mode == layout_mode)
        rows = query.group_by(AnswerRegion.answer_sheet_id).all()
        return {sheet_id: (total, confirmed) for sheet_id, total, confirmed in rows}

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
