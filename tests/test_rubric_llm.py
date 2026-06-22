"""
루브릭 LLM 추천 기능 단독 테스트.
DB/Celery 없이 Claude API 연동만 검증합니다.

실행: python tests/test_rubric_llm.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.workers.rubric_tasks import _call_claude_for_rubric

# --- 테스트 입력값 ---
LABEL = "3번"
PROBLEM_TYPE = "DESCRIPTIVE"  # MULTIPLE_CHOICE | SHORT_ANSWER | DESCRIPTIVE | CODING
MAX_SCORE = 10
MODEL_ANSWER_TEXT = """
광합성은 식물이 빛에너지를 이용하여 이산화탄소와 물을 유기물(포도당)과 산소로 전환하는 과정이다.
반응식: 6CO₂ + 6H₂O + 빛에너지 → C₆H₁₂O₆ + 6O₂
광합성은 엽록체에서 일어나며 명반응과 암반응(캘빈 회로)으로 구분된다.
명반응에서는 빛에너지로 ATP와 NADPH를 생성하고 물을 분해하여 산소를 방출한다.
암반응에서는 ATP와 NADPH를 이용하여 이산화탄소를 고정하고 포도당을 합성한다.
"""

if __name__ == "__main__":
    if not settings.ANTHROPIC_API_KEY:
        print("오류: .env에 ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"Claude API 호출 중... (모델: claude-sonnet-4-6)")
    print(f"문제: {LABEL} / 유형: {PROBLEM_TYPE} / 배점: {MAX_SCORE}점\n")

    try:
        criteria = _call_claude_for_rubric(
            api_key=settings.ANTHROPIC_API_KEY,
            label=LABEL,
            problem_type=PROBLEM_TYPE,
            max_score=MAX_SCORE,
            model_answer_text=MODEL_ANSWER_TEXT,
        )

        total = sum(c["allocated_score"] for c in criteria)
        print(f"생성된 루브릭 기준 ({len(criteria)}개, 합계: {total}점/{MAX_SCORE}점)")
        print("-" * 60)
        for i, c in enumerate(criteria, 1):
            print(f"[{i}] ({c['allocated_score']}점) {c['text']}")

        if total != MAX_SCORE:
            print(f"\n경고: 배점 합계({total}점)가 총점({MAX_SCORE}점)과 다릅니다.")

    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)
