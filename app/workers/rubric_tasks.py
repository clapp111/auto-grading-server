from datetime import datetime, timezone

from app.workers.tasks import celery_app
from app.workers.utils import _build_progress

_PROBLEM_TYPE_LABELS = {
    "MULTIPLE_CHOICE": "객관식",
    "SHORT_ANSWER": "단답형",
    "DESCRIPTIVE": "서술형",
    "CODING": "코딩",
}


@celery_app.task(bind=True, max_retries=3)
def suggest_rubric_task(self, job_id: int):
    import app.db.models  # noqa: F401 - 모든 모델을 SQLAlchemy 레지스트리에 등록
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.enums.rubric_source import RubricSource
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.models.rubric import Rubric

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 3, "PREPARING", "루브릭 추천을 준비 중입니다.")
        db.commit()

        problem = job.problem
        model_answer = (
            db.query(ModelAnswer)
            .filter(ModelAnswer.problem_id == problem.problem_id)
            .first()
        )

        if not model_answer or not model_answer.model_answer_text:
            raise ValueError("모범답안 텍스트가 없습니다. 먼저 모범답안 OCR을 실행해주세요.")

        job.progress_json = _build_progress(1, 3, "ANALYZING", "문제와 모범답안을 분석 중입니다.")
        db.commit()

        criteria = _call_claude_for_rubric(
            api_key=settings.ANTHROPIC_API_KEY,
            label=problem.label,
            problem_type=problem.type.value,
            max_score=problem.max_score,
            problem_text=problem.problem_text,
            model_answer_text=model_answer.model_answer_text,
        )

        job.progress_json = _build_progress(2, 3, "SAVING", "추천 루브릭을 저장하는 중입니다.")
        db.commit()

        # 기존 LLM 추천 기준만 교체한다. 사람이 직접 입력한 HUMAN 기준은 유지한다.
        db.query(Rubric).filter(
            Rubric.problem_id == problem.problem_id,
            Rubric.source == RubricSource.LLM,
        ).delete(synchronize_session=False)

        rubrics = [
            Rubric(
                problem_id=problem.problem_id,
                text=c["text"],
                allocated_score=c["allocated_score"],
                source=RubricSource.LLM,
                order_index=i,
            )
            for i, c in enumerate(criteria)
        ]
        db.add_all(rubrics)

        job.progress_json = _build_progress(3, 3, "DONE", "루브릭 추천이 완료되었습니다.")
        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"generated": len(rubrics)},
            "resultRef": {"type": "rubric", "problemId": problem.problem_id},
        }
        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "루브릭 추천에 실패했습니다.")
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False}
        db.commit()

    finally:
        db.close()


_RUBRIC_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "criteria": {
            "type": "array",
            "description": "채점 기준 목록. allocated_score 합계가 총 배점과 일치해야 합니다.",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "채점 기준 내용"},
                    "allocated_score": {"type": "integer", "description": "해당 기준 배점"},
                },
                "required": ["text", "allocated_score"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["criteria"],
    "additionalProperties": False,
}


def _call_claude_for_rubric(
    api_key: str,
    label: str,
    problem_type: str,
    max_score: int,
    model_answer_text: str,
    problem_text: str | None = None,
) -> list[dict]:
    import json
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    type_label = _PROBLEM_TYPE_LABELS.get(problem_type, problem_type)

    problem_section = f"문제 내용:\n{problem_text}" if problem_text else "문제 내용: (없음)"

    prompt = f"""아래 문제와 모범답안을 분석하여 채점 루브릭 기준들을 생성해주세요.

문제 번호: {label}
문제 유형: {type_label}
총 배점: {max_score}점
{problem_section}
모범답안:
{model_answer_text}

조건:
- 모든 기준의 allocated_score 합계가 정확히 {max_score}점이어야 합니다.
- 각 기준은 충족 여부를 명확히 판단할 수 있는 단위 요소를 써주세요.
- 한국어로 작성해주세요."""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _RUBRIC_JSON_SCHEMA,
            }
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)["criteria"]

    raise ValueError("Claude API로부터 루브릭 기준을 받지 못했습니다.")
