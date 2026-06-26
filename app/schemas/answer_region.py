from pydantic import BaseModel

from app.enums.layout_mode import LayoutMode
from app.enums.region_shape import RegionShape
from app.schemas.common import Point, Region


class RegionTemplateItem(BaseModel):
    problem_id: int
    shape: RegionShape
    bbox_region: Region | None = None
    polygon_points: list[Point] | None = None


class RegionTemplateRequest(BaseModel):
    regions: list[RegionTemplateItem]


class AnswerRegionCreateRequest(BaseModel):
    problem_id: int
    shape: RegionShape
    bbox_region: Region | None = None
    polygon_points: list[Point] | None = None


class AnswerRegionUpdateRequest(BaseModel):
    problem_id: int | None = None
    shape: RegionShape | None = None
    bbox_region: Region | None = None
    polygon_points: list[Point] | None = None


class AnswerRegionResponse(BaseModel):
    answer_region_id: int
    answer_sheet_id: int
    problem_id: int
    problem_label: str
    shape: RegionShape
    bbox_region: Region | None
    polygon_points: list[Point] | None
    layout_mode: LayoutMode

    model_config = {"from_attributes": True}
