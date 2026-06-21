from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── 좌표 / 영역 ────────────────────────────────────────────────

class Region(BaseModel):
    page: int
    x: int
    y: int
    w: int
    h: int


class Point(BaseModel):
    page: int
    x: int
    y: int


# ── 페이지네이션 메타 ───────────────────────────────────────────

class PageMeta(BaseModel):
    type: str = Field(default="page")
    page: int
    size: int
    total_elements: int
    total_pages: int


class SliceMeta(BaseModel):
    type: str = Field(default="slice")
    page: int
    size: int
    has_next: bool


class OffsetMeta(BaseModel):
    type: str = Field(default="offset")
    offset: int
    limit: int
    total: Optional[int] = None


class CursorMeta(BaseModel):
    type: str = Field(default="cursor")
    next_cursor: Optional[str] = None
    has_more: bool


# ── 에러 ───────────────────────────────────────────────────────

class ApiError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


# ── 공통 응답 래퍼 ─────────────────────────────────────────────
# Pydantic v2: GenericModel 제거됨 → BaseModel + Generic[T] 직접 상속

class ApiResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    meta: Optional[Any] = None
    error: Optional[ApiError] = None
