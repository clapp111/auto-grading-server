from app.enums.problem_type import ProblemType
from app.infrastructure.ocr.base import OcrClient
from app.infrastructure.ocr.google_docai_client import GoogleDocAiOcrClient
from app.infrastructure.ocr.naver_clova_client import ClovaOcrClient


def get_ocr_client(problem_type: ProblemType | None = None) -> OcrClient:
    """손코딩(CODING) 답안은 Google Document AI, 그 외는 Naver Clova OCR을 사용한다."""
    if problem_type == ProblemType.CODING:
        return GoogleDocAiOcrClient()
    return ClovaOcrClient()
