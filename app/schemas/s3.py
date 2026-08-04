from pydantic import BaseModel


class PresignedUrlRequest(BaseModel):
    file_name: str
    content_type: str


class PresignedUrlResponse(BaseModel):
    upload_url: str
    file_key: str


class AnswerSheetPresignedUrlResponse(BaseModel):
    upload_url: str
    file_key: str
    answer_sheet_id: int
