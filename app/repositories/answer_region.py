from datetime import datetime, timezone

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

    def get_by_sheet_problem_and_mode(
        self,
        answer_sheet_id: int,
        problem_id: int,
        layout_mode: LayoutMode,
    ) -> AnswerRegion | None:
        return (
            self.db.query(AnswerRegion)
            .options(selectinload(AnswerRegion.problem))
            .filter(
                AnswerRegion.answer_sheet_id == answer_sheet_id,
                AnswerRegion.problem_id == problem_id,
                AnswerRegion.layout_mode == layout_mode,
            )
            .first()
        )

    def list_by_answer_sheet(
        self,
        answer_sheet_id: int,
        layout_mode: LayoutMode | None = None,
    ) -> list[AnswerRegion]:
        query = (
            self.db.query(AnswerRegion)
            .options(selectinload(AnswerRegion.problem))
            .filter(AnswerRegion.answer_sheet_id == answer_sheet_id)
        )
        if layout_mode is not None:
            query = query.filter(AnswerRegion.layout_mode == layout_mode)
        return query.order_by(AnswerRegion.answer_region_id).all()

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
        if any(k in kwargs for k in ("bbox_region", "polygon_points", "shape")):
            kwargs["region_updated_at"] = datetime.now(timezone.utc)
        for key, value in kwargs.items():
            setattr(region, key, value)
        self.db.commit()
        self.db.refresh(region)
        return region

    def delete(self, region: AnswerRegion) -> None:
        self.db.delete(region)
        self.db.commit()

    def delete_all_by_answer_sheet(
        self,
        answer_sheet_id: int,
        layout_mode: LayoutMode | None = None,
        commit: bool = True,
    ) -> None:
        query = self.db.query(AnswerRegion).filter(
            AnswerRegion.answer_sheet_id == answer_sheet_id
        )
        if layout_mode is not None:
            query = query.filter(AnswerRegion.layout_mode == layout_mode)
        query.delete(synchronize_session=False)
        if commit:
            self.db.commit()
