from datetime import datetime, timezone

from app.workers.tasks import celery_app
from app.workers.utils import _build_progress


@celery_app.task(bind=True, max_retries=3)
def apply_region_template(self, job_id: int):
    import app.db.models  # noqa: F401
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.models.answer_region import AnswerRegion
    from app.models.answer_sheet import AnswerSheet
    from app.models.job import Job

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 0, "PREPARING", "템플릿 적용을 준비 중입니다.")
        db.commit()

        exam = job.exam
        sheets = (
            db.query(AnswerSheet)
            .filter(AnswerSheet.exam_id == exam.exam_id)
            .order_by(AnswerSheet.answer_sheet_id)
            .all()
        )

        if not sheets:
            raise ValueError("답안지가 없습니다.")

        template_sheet = sheets[0]
        target_sheets = sheets[1:]
        total = len(target_sheets)

        template_regions = (
            db.query(AnswerRegion)
            .filter(AnswerRegion.answer_sheet_id == template_sheet.answer_sheet_id)
            .all()
        )

        # db.commit()마다 ORM 객체가 expire되므로 루프 전에 plain dict로 추출
        template_data = [
            {
                "problem_id": r.problem_id,
                "shape": r.shape,
                "layout_mode": r.layout_mode,
                "bbox_region": r.bbox_region,
                "polygon_points": r.polygon_points,
            }
            for r in template_regions
        ]

        job.progress_json = _build_progress(0, total, "APPLYING", f"0/{total} 답안지에 템플릿을 적용 중입니다.")
        db.commit()

        for index, sheet in enumerate(target_sheets, start=1):
            db.query(AnswerRegion).filter(
                AnswerRegion.answer_sheet_id == sheet.answer_sheet_id
            ).delete()

            for tmpl in template_data:
                db.add(AnswerRegion(
                    answer_sheet_id=sheet.answer_sheet_id,
                    **tmpl,
                ))

            if index % max(1, total // 10) == 0 or index == total:
                job.progress_json = _build_progress(index, total, "APPLYING", f"{index}/{total} 답안지에 템플릿을 적용 중입니다.")

            db.commit()

        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        job.progress_json = _build_progress(total, total, "DONE", "템플릿 적용이 완료되었습니다.")
        job.result_json = {
            "summary": {"processed": total, "succeeded": total, "failed": 0},
            "resultRef": {"type": "answer_regions", "examId": exam.exam_id},
        }
        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "템플릿 적용에 실패했습니다.")
        job.error_json = {
            "code": "INTERNAL",
            "message": str(e),
            "retryable": False,
            "category": "internal",
        }
        db.commit()

    finally:
        db.close()
