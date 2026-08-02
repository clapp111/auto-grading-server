import json
from datetime import datetime, timezone

from app.workers.tasks import celery_app
from app.workers.utils import _build_progress

_PROBLEM_TYPE_LABELS = {
    "MULTIPLE_CHOICE": "객관식",
    "SHORT_ANSWER": "단답형",
    "DESCRIPTIVE": "서술형",
    "CODING": "손코딩",
}


# ===========================================================================
# ============================== 주요 워커 기능 ==============================
# ===========================================================================


@celery_app.task(bind=True, max_retries=3)
def run_llm_grade(self, job_id: int):
    """루브릭 기준에 따라 서술형·손코딩 답안을 LLM으로 채점한다.

    학생별 OCR 답안을 병렬로 Claude에 보내 기준 충족 여부를 받고, 만족한 기준의 배점
    합으로 점수를 매긴 뒤 SUGGESTED 상태로 저장한다. 일부 학생만 실패하면 부분 실패로
    기록하고, 외부 API 연결·레이트리밋 오류는 백오프 후 재시도한다. 그 외 내부 오류는
    FAILED로 기록한다.

    Args:
        job_id: 처리할 LLM 채점 잡 ID

    Raises:
        APIConnectionError: Claude 연결 실패로 재시도가 필요한 경우 (지수 백오프)
        RateLimitError: Claude 레이트리밋으로 재시도가 필요한 경우 (선형 백오프)
    """
    import anthropic

    import app.db.models  # noqa: F401
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.enums.grade_method import GradeMethod
    from app.enums.grade_status import GradeStatus
    from app.enums.job_status import JobStatus
    from app.enums.problem_type import ProblemType
    from app.models.answer_region import AnswerRegion
    from app.models.answer_sheet import AnswerSheet
    from app.models.exam import Exam
    from app.models.grade import Grade
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.models.ocr_result import OCRResult
    from app.models.problem import Problem
    from app.models.rubric import Rubric
    from app.models.student import Student

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(
            0, 0, "PREPARING", "LLM 채점을 준비 중입니다."
        )
        db.commit()

        problem = db.get(Problem, job.problem_id)
        exam = db.get(Exam, job.exam_id)
        if not problem:
            raise ValueError("채점 대상 문제가 삭제되었습니다.")
        if not exam:
            raise ValueError("채점 대상 시험이 삭제되었습니다.")

        if problem.type not in (ProblemType.DESCRIPTIVE, ProblemType.CODING):
            raise ValueError("LLM 채점은 서술형/손코딩 문제에만 지원됩니다.")

        model_answer = (
            db.query(ModelAnswer)
            .filter(ModelAnswer.problem_id == problem.problem_id)
            .first()
        )
        if not model_answer or not model_answer.model_answer_text:
            raise ValueError("모범답안이 등록되지 않았습니다.")

        rubrics = (
            db.query(Rubric)
            .filter(Rubric.problem_id == problem.problem_id)
            .order_by(Rubric.order_index)
            .all()
        )
        if not rubrics:
            raise ValueError("채점 루브릭이 등록되지 않았습니다.")

        # expire_on_commit 영향을 받지 않도록 plain value/dict로 추출
        problem_id = problem.problem_id
        problem_label = problem.label
        problem_type_value = problem.type.value
        max_score = problem.max_score
        model_answer_text = model_answer.model_answer_text
        rubric_data = [
            {
                "rubric_id": r.rubric_id,
                "text": r.text,
                "allocated_score": r.allocated_score,
            }
            for r in rubrics
        ]

        rows = (
            db.query(Student, OCRResult)
            .join(AnswerSheet, AnswerSheet.student_id == Student.student_id)
            .join(
                AnswerRegion,
                AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id,
            )
            .join(
                OCRResult, OCRResult.answer_region_id == AnswerRegion.answer_region_id
            )
            .filter(
                Student.exam_id == exam.exam_id,
                AnswerRegion.problem_id == problem.problem_id,
                AnswerRegion.layout_mode == exam.layout_mode,
            )
            .all()
        )

        targets = [
            {
                "student_id": s.student_id,
                "student_name": s.name,
                "ocr_text": o.text or "",
            }
            for s, o in rows
        ]

        total = len(targets)
        if total == 0:
            job.status = JobStatus.DONE
            job.completed_at = datetime.now(timezone.utc)
            job.progress_json = _build_progress(0, 0, "DONE", "채점할 답안이 없습니다.")
            job.result_json = {"summary": {"processed": 0, "succeeded": 0, "failed": 0}}
            db.commit()
            return

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        succeeded = 0
        failed = 0
        failed_targets: list[dict] = []

        job.progress_json = _build_progress(
            0, total, "GRADING", "LLM 채점을 시작합니다."
        )
        db.commit()

        grade_results: dict[int, dict] = {}
        grade_errors: dict[int, str] = {}
        pending_retry: Exception | None = None
        progress_interval = max(1, (total + 9) // 10)

        def _grade_one(t: dict) -> tuple[int, dict]:
            result = _call_claude_for_grade(
                client=client,
                label=problem_label,
                problem_type=problem_type_value,
                max_score=max_score,
                model_answer_text=model_answer_text,
                rubric_data=rubric_data,
                student_answer=t["ocr_text"],
            )
            return t["student_id"], result

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=min(total, 5)) as executor:
            future_to_target = {executor.submit(_grade_one, t): t for t in targets}
            completed = 0
            for completed, future in enumerate(as_completed(future_to_target), start=1):
                t = future_to_target[future]
                try:
                    student_id, result = future.result()
                    grade_results[student_id] = result
                except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
                    if pending_retry is None:
                        pending_retry = e
                except Exception as e:  # noqa: BLE001
                    grade_errors[t["student_id"]] = str(e)

                if completed % progress_interval == 0 or completed == total:
                    job.progress_json = _build_progress(
                        completed,
                        total,
                        "GRADING",
                        f"{completed}/{total} 답안을 채점 중입니다.",
                    )
                    db.commit()

        if pending_retry is not None:
            raise pending_retry

        rubric_map = {r["rubric_id"]: r["allocated_score"] for r in rubric_data}
        for t in targets:
            student_id = t["student_id"]
            if student_id in grade_errors:
                failed += 1
                failed_targets.append(
                    {"studentId": student_id, "reason": grade_errors[student_id]}
                )
                continue
            if student_id not in grade_results:
                continue

            result = grade_results[student_id]
            score = sum(
                rubric_map.get(r["rubric_id"], 0)
                for r in result["rubric_results"]
                if r["satisfied"]
            )
            breakdown = [
                {"rubric_id": r["rubric_id"], "satisfied": r["satisfied"]}
                for r in result["rubric_results"]
            ]

            existing = (
                db.query(Grade)
                .filter(Grade.problem_id == problem_id, Grade.student_id == student_id)
                .first()
            )
            if existing:
                existing.score = score
                existing.comment = result["comment"]
                existing.rubric_breakdown = breakdown
                existing.method = GradeMethod.LLM
                existing.status = GradeStatus.SUGGESTED
            else:
                db.add(
                    Grade(
                        problem_id=problem_id,
                        student_id=student_id,
                        score=score,
                        comment=result["comment"],
                        rubric_breakdown=breakdown,
                        method=GradeMethod.LLM,
                        status=GradeStatus.SUGGESTED,
                    )
                )

            succeeded += 1

        db.commit()

        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": total, "succeeded": succeeded, "failed": failed},
            "resultRef": {"type": "grades", "problemId": problem_id},
        }

        if failed > 0:
            job.status = JobStatus.FAILED
            job.progress_json = _build_progress(
                total, total, "FAILED", "일부 답안의 LLM 채점에 실패했습니다."
            )
            job.error_json = {
                "code": "PARTIAL_LLM_GRADE_FAILED",
                "message": "일부 답안의 LLM 채점에 실패했습니다.",
                "retryable": False,
                "category": "provider",
                "failedTargets": failed_targets,
            }
        else:
            job.status = JobStatus.DONE
            job.progress_json = _build_progress(
                total, total, "DONE", "LLM 채점이 완료되었습니다."
            )

        db.commit()

    except anthropic.APIConnectionError as e:
        raise self.retry(exc=e, countdown=2**self.request.retries)

    except anthropic.RateLimitError as e:
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))

    except Exception as e:  # noqa: BLE001
        db.rollback()
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "LLM 채점에 실패했습니다.")
        job.error_json = {
            "code": "INTERNAL",
            "message": str(e),
            "retryable": False,
            "category": "internal",
        }
        db.commit()

    finally:
        db.close()


# ===========================================================================
# ================================ 헬퍼 함수 ================================
# ===========================================================================


_GRADE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "rubric_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rubric_id": {"type": "integer"},
                    "satisfied": {"type": "boolean"},
                },
                "required": ["rubric_id", "satisfied"],
                "additionalProperties": False,
            },
        },
        "comment": {"type": "string", "description": "학생 답안에 대한 종합 피드백"},
    },
    "required": ["rubric_results", "comment"],
    "additionalProperties": False,
}


def _call_claude_for_grade(
    client,
    label: str,
    problem_type: str,
    max_score: int,
    model_answer_text: str,
    rubric_data: list[dict],
    student_answer: str,
) -> dict:
    """Claude API를 호출해 학생 답안의 기준 충족 여부와 피드백을 받는다.

    각 루브릭 기준의 충족 여부와 감점 사유 위주의 종합 피드백을 JSON 스키마로 강제해 받는다.

    Args:
        client: Anthropic 클라이언트
        label: 문제 번호(라벨)
        problem_type: 문제 유형 코드 (예: DESCRIPTIVE)
        max_score: 문제 총 배점
        model_answer_text: 모범답안 텍스트
        rubric_data: rubric_id·text·allocated_score를 담은 채점 기준 목록
        student_answer: 학생 답안 OCR 텍스트

    Returns:
        rubric_results(기준별 충족 여부)와 comment(종합 피드백)를 담은 채점 결과 딕셔너리

    Raises:
        ValueError: Claude 응답에서 채점 결과를 받지 못한 경우
    """
    type_label = _PROBLEM_TYPE_LABELS.get(problem_type, problem_type)
    rubric_lines = "\n".join(
        f"- [rubric_id={r['rubric_id']}] {r['text']} ({r['allocated_score']}점)"
        for r in rubric_data
    )

    prompt = f"""아래 정보를 바탕으로 학생 답안을 채점해주세요.

문제 번호: {label}
문제 유형: {type_label}
총 배점: {max_score}점

모범답안:
{model_answer_text}

채점 기준:
{rubric_lines}

학생 답안:
{student_answer}

각 채점 기준에 대해 학생 답안이 충족하는지 판단하고, 종합 피드백을 작성해주세요.
한국어로 작성해주세요. 종합 피드백은 학생이 감점된 이유만 300자 이내로 작성해주세요."""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _GRADE_JSON_SCHEMA,
            }
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)

    raise ValueError("Claude API로부터 채점 결과를 받지 못했습니다.")
