from sqlalchemy.orm import Session, selectinload

from app.enums.layout_mode import LayoutMode
from app.enums.region_shape import RegionShape
from app.models.answer_region import AnswerRegion


class AnswerRegionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, answer_region_id: int) -> AnswerRegion | None:
        return (
            self.db.query(AnswerRegion)
            .options(selectinload(AnswerRegion.problem))
            .filter(AnswerRegion.answer_region_id == answer_region_id)
            .first()
        )

    def list_by_answer_sheet(self, answer_sheet_id: int) -> list[AnswerRegion]:
        return (
            self.db.query(AnswerRegion)
            .options(selectinload(AnswerRegion.problem))
            .filter(AnswerRegion.answer_sheet_id == answer_sheet_id)
            .order_by(AnswerRegion.answer_region_id)
            .all()
        )

    def create(
        self,
        answer_sheet_id: int,
        problem_id: int,
        shape: RegionShape,
        layout_mode: LayoutMode,
        bbox_region: dict | None = None,
        polygon_points: list | None = None,
    ) -> AnswerRegion:
        region = AnswerRegion(
            answer_sheet_id=answer_sheet_id,
            problem_id=problem_id,
            shape=shape,
            layout_mode=layout_mode,
            bbox_region=bbox_region,
            polygon_points=polygon_points,
        )
        self.db.add(region)
        self.db.commit()
        self.db.refresh(region)
        return region

    def update(self, region: AnswerRegion, **kwargs) -> AnswerRegion:
        for key, value in kwargs.items():
            setattr(region, key, value)
        self.db.commit()
        self.db.refresh(region)
        return region

    def delete(self, region: AnswerRegion) -> None:
        self.db.delete(region)
        self.db.commit()

    def delete_all_by_answer_sheet(self, answer_sheet_id: int) -> None:
        self.db.query(AnswerRegion).filter(
            AnswerRegion.answer_sheet_id == answer_sheet_id
        ).delete()
        self.db.commit()
