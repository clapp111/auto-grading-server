from pydantic import BaseModel, ConfigDict

from app.enums.programming_language import ProgrammingLanguage
from app.schemas.common import Region


# ── 서브스텝 2/3: 모범답안 OCR ─────────────────────────────────

class ModelAnswerOcrRequest(BaseModel):
    region: Region                                # 모범답안 파일에서 드래그한 영역
    language: ProgrammingLanguage | None = None   # CODING 유형 시 필수


# ── 서브스텝 3/3: 정답 입력·확정 ───────────────────────────────
# 유형별 유효 필드는 서비스 레이어에서 Problem.type 기준으로 검증

class ModelAnswerUpdateRequest(BaseModel):
    correct_choice: int | None = None             # 객관식 — 정답 번호
    choice_count: int | None = None               # 객관식 — 보기 개수
    accepted_answers: list[str] | None = None     # 단답형 — 허용 정답 목록
    model_answer_text: str | None = None          # 서술/손코딩 — OCR 후 수정·확정 텍스트
    region: Region | None = None                  # 모범답안 파일 내 영역 업데이트


class ModelAnswerResponse(BaseModel):
    model_answer_id: int | None
    problem_id: int
    correct_choice: int | None
    choice_count: int | None
    accepted_answers: list[str] | None
    model_answer_text: str | None
    region: Region | None

    model_config = ConfigDict(from_attributes=True)
