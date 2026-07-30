"""
루브릭 LLM 추천 기능 테스트.

실행 (단위):   pytest tests/test_rubric.py -v
실행 (통합):   pytest tests/test_rubric.py -v -m integration
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from unittest.mock import MagicMock, patch

import pytest

from app.workers.rubric_tasks import _call_claude_for_rubric

# ── Mock 데이터 ─────────────────────────────────────────────────

API_KEY = "test-api-key"
LABEL = "3번"
PROBLEM_TYPE = "DESCRIPTIVE"
MAX_SCORE = 10
MODEL_ANSWER_TEXT = """
광합성은 식물이 빛에너지를 이용하여 이산화탄소와 물을 유기물(포도당)과 산소로 전환하는 과정이다.
반응식: 6CO₂ + 6H₂O + 빛에너지 → C₆H₁₂O₆ + 6O₂
"""

MOCK_CRITERIA = [
    {"text": "광합성의 정의를 정확히 서술하였다.", "allocated_score": 4},
    {"text": "반응식을 올바르게 기재하였다.", "allocated_score": 3},
    {"text": "명반응과 암반응을 구분하여 설명하였다.", "allocated_score": 3},
]


# ── 헬퍼 ─────────────────────────────────────────────────────────


def make_mock_stream(criteria: list[dict]) -> MagicMock:
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = json.dumps({"criteria": criteria})

    response = MagicMock()
    response.content = [text_block]

    stream = MagicMock()
    stream.__enter__ = MagicMock(return_value=stream)
    stream.__exit__ = MagicMock(return_value=False)
    stream.get_final_message.return_value = response

    return stream


# ── 단위 테스트 ───────────────────────────────────────────────────


class TestCallClaudeForRubric:
    @pytest.fixture
    def mock_client(self):
        with patch("anthropic.Anthropic") as MockAnthropic:
            client = MagicMock()
            MockAnthropic.return_value = client
            client.messages.stream.return_value = make_mock_stream(MOCK_CRITERIA)
            yield client

    def test_returns_criteria_list(self, mock_client):
        result = _call_claude_for_rubric(
            API_KEY, LABEL, PROBLEM_TYPE, MAX_SCORE, MODEL_ANSWER_TEXT
        )

        assert isinstance(result, list)
        assert len(result) == len(MOCK_CRITERIA)

    def test_criteria_have_required_fields(self, mock_client):
        result = _call_claude_for_rubric(
            API_KEY, LABEL, PROBLEM_TYPE, MAX_SCORE, MODEL_ANSWER_TEXT
        )

        for c in result:
            assert "text" in c
            assert "allocated_score" in c
            assert isinstance(c["text"], str)
            assert isinstance(c["allocated_score"], int)

    def test_prompt_includes_label_and_score(self, mock_client):
        _call_claude_for_rubric(
            API_KEY, LABEL, PROBLEM_TYPE, MAX_SCORE, MODEL_ANSWER_TEXT
        )

        _, kwargs = mock_client.messages.stream.call_args
        prompt = kwargs["messages"][0]["content"]
        assert LABEL in prompt
        assert str(MAX_SCORE) in prompt

    def test_prompt_includes_model_answer(self, mock_client):
        _call_claude_for_rubric(
            API_KEY, LABEL, PROBLEM_TYPE, MAX_SCORE, MODEL_ANSWER_TEXT
        )

        _, kwargs = mock_client.messages.stream.call_args
        prompt = kwargs["messages"][0]["content"]
        assert MODEL_ANSWER_TEXT.strip() in prompt

    def test_raises_when_no_text_block_in_response(self):
        thinking_block = MagicMock()
        thinking_block.type = "thinking"

        response = MagicMock()
        response.content = [thinking_block]

        stream = MagicMock()
        stream.__enter__ = MagicMock(return_value=stream)
        stream.__exit__ = MagicMock(return_value=False)
        stream.get_final_message.return_value = response

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.stream.return_value = stream

            with pytest.raises(ValueError, match="루브릭 기준을 받지 못했습니다"):
                _call_claude_for_rubric(
                    API_KEY, LABEL, PROBLEM_TYPE, MAX_SCORE, MODEL_ANSWER_TEXT
                )


# ── 통합 테스트 (실제 Claude API 호출) ──────────────────────────────


@pytest.mark.integration
class TestCallClaudeForRubricIntegration:
    def test_claude_returns_valid_rubric(self):
        from app.core.config import settings

        if not settings.ANTHROPIC_API_KEY:
            pytest.skip(".env에 ANTHROPIC_API_KEY가 없습니다.")

        result = _call_claude_for_rubric(
            api_key=settings.ANTHROPIC_API_KEY,
            label=LABEL,
            problem_type=PROBLEM_TYPE,
            max_score=MAX_SCORE,
            model_answer_text=MODEL_ANSWER_TEXT,
        )

        assert len(result) > 0
        total = sum(c["allocated_score"] for c in result)
        assert total == MAX_SCORE, f"배점 합계 불일치: {total} != {MAX_SCORE}"
        for c in result:
            assert c["text"]
            assert c["allocated_score"] > 0
