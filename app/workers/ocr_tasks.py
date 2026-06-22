import requests
from datetime import datetime

from app.workers.tasks import celery_app


@celery_app.task(bind=True, max_retries=3)
def run_model_answer_ocr(self, job_id: int):
    import app.db.models  # noqa: F401 - 모든 모델을 SQLAlchemy 레지스트리에 등록
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.infrastructure.ocr.ocr_client import ClovaOcrClient
    from app.infrastructure.pdf.renderer import crop_region
    from app.infrastructure.storage.deps import get_storage
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.schemas.common import Region

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        problem = job.problem
        exam = job.exam
        model_answer = db.query(ModelAnswer).filter(ModelAnswer.problem_id == problem.problem_id).first()

        if not model_answer or not model_answer.region:
            raise ValueError("OCR 대상 region이 지정되지 않았습니다.")
        if not exam.model_answer_file_key:
            raise ValueError("모범답안 파일이 업로드되지 않았습니다.")

        region = Region(**model_answer.region)
        storage = get_storage()
        pdf_bytes = storage.download(exam.model_answer_file_key)

        image_bytes = crop_region(pdf_bytes, region.page, region.x, region.y, region.w, region.h)

        ocr_client = ClovaOcrClient()
        extracted_text = ocr_client.recognize(image_bytes)

        model_answer.model_answer_text = extracted_text
        job.status = JobStatus.DONE
        job.completed_at = datetime.utcnow()
        job.result_json = {
            "summary": {"processed": 1, "succeeded": 1, "failed": 0},
            "resultRef": {"type": "model_answer", "problemId": problem.problem_id},
        }
        db.commit()

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False}
        db.commit()

    finally:
        db.close()
