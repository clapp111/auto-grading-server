from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "auto_grading",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.ocr_tasks", "app.workers.rubric_tasks", "app.workers.region_tasks", "app.workers.grade_tasks"],
)
