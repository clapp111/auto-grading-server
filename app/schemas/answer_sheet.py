from pydantic import BaseModel

from app.enums.sheet_status import SheetStatus
from app.schemas.common import Region


class AnswerSheetResponse(BaseModel):
    answer_sheet_id: int
    exam_id: int
    file_key: str
    status: SheetStatus
    student_id: int | None
    student_name: str | None
    student_no: str | None


class AnswerSheetDownloadResponse(BaseModel):
    url: str
    student_name_region: Region | None = None
    student_no_region: Region | None = None


class AnswerSheetPatchRequest(BaseModel):
    name: str | None = None
    student_no: str | None = None


class IdRegionSaveRequest(BaseModel):
    name_region: Region
    student_no_region: Region


class UploadCompleteResponse(BaseModel):
    answer_sheet_id: int
    job_id: int | None = None
