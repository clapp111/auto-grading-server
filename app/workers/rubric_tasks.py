from datetime import datetime

from app.workers.tasks import celery_app

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
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        problem = job.problem
        model_answer = (
            db.query(ModelAnswer)
            .filter(ModelAnswer.problem_id == problem.problem_id)
            .first()
        )

        if not model_answer or not model_answer.model_answer_text:
            raise ValueError("모범답안 텍스트가 없습니다. 먼저 모범답안 OCR을 실행해주세요.")

        criteria = _call_claude_for_rubric(
            api_key=settings.ANTHROPIC_API_KEY,
            label=problem.label,
            problem_type=problem.type.value,
            max_score=problem.max_score,
            model_answer_text=model_answer.model_answer_text,
        )

        # 기존 LLM 추천 기준만 교체 (사용자가 직접 입력한 HUMAN 기준은 유지)
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

        job.status = JobStatus.DONE
        job.completed_at = datetime.utcnow()
        job.result_json = {
            "summary": {"generated": len(rubrics)},
            "resultRef": {"type": "rubric", "problemId": problem.problem_id},
        }
        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED
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
                    "text": {"type": "string", "description": "채점 기준 내용 (한국어)"},
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
) -> list[dict]:
    import json
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    type_label = _PROBLEM_TYPE_LABELS.get(problem_type, problem_type)

    prompt = f"""아래 문제와 모범답안을 분석하여 채점 루브릭 기준을 생성해주세요.

문제 번호: {label}
문제 유형: {type_label}
총 배점: {max_score}점

모범답안:
{model_answer_text}

조건:
- 모든 기준의 allocated_score 합계가 정확히 {max_score}점이어야 합니다.
- 각 기준은 충족 여부를 명확히 판단할 수 있는 단일 요소를 다루세요.
- 한국어로 작성하세요."""

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
