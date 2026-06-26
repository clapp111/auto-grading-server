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


@celery_app.task(bind=True, max_retries=3)
def run_auto_grade(self, job_id: int):
    import app.db.models  # noqa: F401
    from app.db.session import SessionLocal
    from app.enums.grade_method import GradeMethod
    from app.enums.grade_status import GradeStatus
    from app.enums.job_status import JobStatus
    from app.enums.problem_type import ProblemType
    from app.models.answer_region import AnswerRegion
    from app.models.answer_sheet import AnswerSheet
    from app.models.grade import Grade
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.models.ocr_result import OCRResult
    from app.models.student import Student

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 0, "PREPARING", "자동 채점을 준비 중입니다.")
        db.commit()

        problem = job.problem
        exam = job.exam

        model_answer = (
            db.query(ModelAnswer)
            .filter(ModelAnswer.problem_id == problem.problem_id)
            .first()
        )
        if not model_answer or not model_answer.model_answer_text:
            raise ValueError("모범답안이 등록되지 않았습니다.")

        # OCR 결과가 있는 학생만 대상으로 단일 JOIN 쿼리
        rows = (
            db.query(Student, OCRResult)
            .join(AnswerSheet, AnswerSheet.student_id == Student.student_id)
            .join(AnswerRegion, AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id)
            .join(OCRResult, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .filter(
                Student.exam_id == exam.exam_id,
                AnswerRegion.problem_id == problem.problem_id,
            )
            .all()
        )

        # expire_on_commit 영향을 받지 않도록 plain dict로 추출
        targets = [
            {
                "student_id": s.student_id,
                "marked_choice": o.marked_choice,
                "text": o.text,
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

        # expire_on_commit 영향을 받지 않도록 plain value로 추출
        problem_id = problem.problem_id
        max_score = problem.max_score
        correct_answer = model_answer.model_answer_text
        is_mc = problem.type == ProblemType.MULTIPLE_CHOICE
        correct_choice = _parse_choice(correct_answer) if is_mc else None

        succeeded = 0
        failed = 0
        failed_targets: list[dict] = []

        job.progress_json = _build_progress(0, total, "GRADING", "자동 채점을 시작합니다.")
        db.commit()

        for index, t in enumerate(targets, start=1):
            try:
                if is_mc:
                    correct = (t["marked_choice"] is not None and t["marked_choice"] == correct_choice)
                else:
                    correct = _normalize_text(t["text"] or "") == _normalize_text(correct_answer)

                score = max_score if correct else 0

                existing = (
                    db.query(Grade)
                    .filter(Grade.problem_id == problem_id, Grade.student_id == t["student_id"])
                    .first()
                )
                if existing:
                    existing.score = score
                    existing.method = GradeMethod.AUTO
                    existing.status = GradeStatus.SUGGESTED
                    existing.rubric_breakdown = None
                    existing.comment = None
                else:
                    db.add(Grade(
                        problem_id=problem_id,
                        student_id=t["student_id"],
                        score=score,
                        method=GradeMethod.AUTO,
                        status=GradeStatus.SUGGESTED,
                    ))

                succeeded += 1

            except Exception as e:
                failed += 1
                failed_targets.append({"studentId": t["student_id"], "reason": str(e)})

            if index % max(1, total // 10) == 0 or index == total:
                job.progress_json = _build_progress(index, total, "GRADING", f"{index}/{total} 답안을 채점 중입니다.")
                db.commit()

        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": total, "succeeded": succeeded, "failed": failed},
            "resultRef": {"type": "grades", "problemId": problem_id},
        }

        if failed > 0:
            job.status = JobStatus.FAILED
            job.progress_json = _build_progress(total, total, "FAILED", "일부 답안의 자동 채점에 실패했습니다.")
            job.error_json = {
                "code": "PARTIAL_AUTO_GRADE_FAILED",
                "message": "일부 답안의 자동 채점에 실패했습니다.",
                "retryable": False,
                "category": "internal",
                "failedTargets": failed_targets,
            }
        else:
            job.status = JobStatus.DONE
            job.progress_json = _build_progress(total, total, "DONE", "자동 채점이 완료되었습니다.")

        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "자동 채점에 실패했습니다.")
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False, "category": "internal"}
        db.commit()

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_llm_grade(self, job_id: int):
    import anthropic
    import app.db.models  # noqa: F401
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.enums.grade_method import GradeMethod
    from app.enums.grade_status import GradeStatus
    from app.enums.job_status import JobStatus
    from app.models.answer_region import AnswerRegion
    from app.models.answer_sheet import AnswerSheet
    from app.models.grade import Grade
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.models.ocr_result import OCRResult
    from app.models.rubric import Rubric
    from app.models.student import Student

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 0, "PREPARING", "LLM 채점을 준비 중입니다.")
        db.commit()

        problem = job.problem
        exam = job.exam

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
            {"rubric_id": r.rubric_id, "text": r.text, "allocated_score": r.allocated_score}
            for r in rubrics
        ]

        rows = (
            db.query(Student, OCRResult)
            .join(AnswerSheet, AnswerSheet.student_id == Student.student_id)
            .join(AnswerRegion, AnswerRegion.answer_sheet_id == AnswerSheet.answer_sheet_id)
            .join(OCRResult, OCRResult.answer_region_id == AnswerRegion.answer_region_id)
            .filter(
                Student.exam_id == exam.exam_id,
                AnswerRegion.problem_id == problem.problem_id,
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

        job.progress_json = _build_progress(0, total, "GRADING", "LLM 채점을 시작합니다.")
        db.commit()

        for index, t in enumerate(targets, start=1):
            try:
                result = _call_claude_for_grade(
                    client=client,
                    label=problem_label,
                    problem_type=problem_type_value,
                    max_score=max_score,
                    model_answer_text=model_answer_text,
                    rubric_data=rubric_data,
                    student_answer=t["ocr_text"],
                )

                rubric_map = {r["rubric_id"]: r["allocated_score"] for r in rubric_data}
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
                    .filter(Grade.problem_id == problem_id, Grade.student_id == t["student_id"])
                    .first()
                )
                if existing:
                    existing.score = score
                    existing.comment = result["comment"]
                    existing.rubric_breakdown = breakdown
                    existing.method = GradeMethod.LLM
                    existing.status = GradeStatus.SUGGESTED
                else:
                    db.add(Grade(
                        problem_id=problem_id,
                        student_id=t["student_id"],
                        score=score,
                        comment=result["comment"],
                        rubric_breakdown=breakdown,
                        method=GradeMethod.LLM,
                        status=GradeStatus.SUGGESTED,
                    ))

                succeeded += 1

            except anthropic.APIConnectionError:
                raise  # 외부 except로 전파 → self.retry() 호출

            except anthropic.RateLimitError:
                raise  # 외부 except로 전파 → self.retry() 호출

            except Exception as e:
                failed += 1
                failed_targets.append({"studentId": t["student_id"], "reason": str(e)})

            if index % max(1, total // 10) == 0 or index == total:
                job.progress_json = _build_progress(index, total, "GRADING", f"{index}/{total} 답안을 채점 중입니다.")
                db.commit()

        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": total, "succeeded": succeeded, "failed": failed},
            "resultRef": {"type": "grades", "problemId": problem_id},
        }

        if failed > 0:
            job.status = JobStatus.FAILED
            job.progress_json = _build_progress(total, total, "FAILED", "일부 답안의 LLM 채점에 실패했습니다.")
            job.error_json = {
                "code": "PARTIAL_LLM_GRADE_FAILED",
                "message": "일부 답안의 LLM 채점에 실패했습니다.",
                "retryable": False,
                "category": "provider",
                "failedTargets": failed_targets,
            }
        else:
            job.status = JobStatus.DONE
            job.progress_json = _build_progress(total, total, "DONE", "LLM 채점이 완료되었습니다.")

        db.commit()

    except anthropic.APIConnectionError as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except anthropic.RateLimitError as e:
        raise self.retry(exc=e, countdown=30 * (self.request.retries + 1))

    except Exception as e:
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "LLM 채점에 실패했습니다.")
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False, "category": "internal"}
        db.commit()

    finally:
        db.close()


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
한국어로 작성해주세요."""

    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        thinking={"type": "adaptive"},
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


def _parse_choice(text: str) -> int | None:
    digits = [ch for ch in text if ch.isdigit()]
    return int(digits[0]) if len(digits) == 1 else None


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip().lower()
