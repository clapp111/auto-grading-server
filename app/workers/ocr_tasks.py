import requests
from datetime import datetime, timezone

from app.workers.tasks import celery_app
from app.workers.utils import _build_progress


@celery_app.task(bind=True, max_retries=3)
def run_problem_ocr(self, job_id: int):
    import app.db.models  # noqa: F401
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.infrastructure.ocr.naver_clova_client import ClovaOcrClient
    from app.infrastructure.pdf.renderer import crop_region
    from app.infrastructure.storage.deps import get_storage
    from app.models.exam import Exam
    from app.models.job import Job
    from app.models.problem import Problem
    from app.schemas.common import Region

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 1, "OCR", "문제 OCR을 시작합니다.")
        db.commit()

        problem = db.get(Problem, job.problem_id)
        exam = db.get(Exam, job.exam_id)
        if not problem:
            raise ValueError("OCR 대상 문제가 삭제되었습니다.")
        if not exam:
            raise ValueError("OCR 대상 시험이 삭제되었습니다.")

        if not problem.region:
            raise ValueError("OCR 대상 region이 지정되지 않았습니다.")
        if not exam.problem_sheet_file_key:
            raise ValueError("문제지 파일이 업로드되지 않았습니다.")

        region = Region(**problem.region)
        storage = get_storage()
        pdf_bytes = storage.download(exam.problem_sheet_file_key)

        image_bytes = crop_region(pdf_bytes, region.page, region.x, region.y, region.w, region.h)

        ocr_client = ClovaOcrClient()
        extracted_text = ocr_client.recognize(image_bytes)

        problem.problem_text = extracted_text
        job.progress_json = _build_progress(1, 1, "DONE", "문제 OCR이 완료되었습니다.")
        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": 1, "succeeded": 1, "failed": 0},
            "resultRef": {"type": "problem", "problemId": problem.problem_id},
        }
        db.commit()

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        db.rollback()
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "문제 OCR에 실패했습니다.")
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False}
        db.commit()

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_model_answer_ocr(self, job_id: int):
    import app.db.models  # noqa: F401 - 모든 모델을 SQLAlchemy 레지스트리에 등록
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.infrastructure.ocr.deps import get_ocr_client
    from app.infrastructure.pdf.renderer import crop_region
    from app.infrastructure.storage.deps import get_storage
    from app.models.exam import Exam
    from app.models.job import Job
    from app.models.model_answer import ModelAnswer
    from app.models.problem import Problem
    from app.schemas.common import Region

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 1, "OCR", "모범답안 OCR을 시작합니다.")
        db.commit()

        problem = db.get(Problem, job.problem_id)
        exam = db.get(Exam, job.exam_id)
        if not problem:
            raise ValueError("OCR 대상 문제가 삭제되었습니다.")
        if not exam:
            raise ValueError("OCR 대상 시험이 삭제되었습니다.")

        model_answer = db.query(ModelAnswer).filter(ModelAnswer.problem_id == problem.problem_id).first()

        if not model_answer or not model_answer.region:
            raise ValueError("OCR 대상 region이 지정되지 않았습니다.")
        if not exam.model_answer_file_key:
            raise ValueError("모범답안 파일이 업로드되지 않았습니다.")

        region = Region(**model_answer.region)
        storage = get_storage()
        pdf_bytes = storage.download(exam.model_answer_file_key)

        image_bytes = crop_region(pdf_bytes, region.page, region.x, region.y, region.w, region.h)

        ocr_client = get_ocr_client(problem.type)
        extracted_text = ocr_client.recognize(image_bytes)

        model_answer.model_answer_text = extracted_text
        job.progress_json = _build_progress(1, 1, "DONE", "모범답안 OCR이 완료되었습니다.")
        job.status = JobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": 1, "succeeded": 1, "failed": 0},
            "resultRef": {"type": "model_answer", "problemId": problem.problem_id},
        }
        db.commit()

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        db.rollback()
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "모범답안 OCR에 실패했습니다.")
        job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False}
        db.commit()

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_student_id_ocr(self, job_id: int):
    import app.db.models  # noqa: F401
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.enums.sheet_status import SheetStatus
    from app.infrastructure.ocr.naver_clova_client import ClovaOcrClient
    from app.infrastructure.pdf.renderer import crop_region
    from app.infrastructure.storage.deps import get_storage
    from app.models.answer_sheet import AnswerSheet
    from app.models.exam import Exam
    from app.models.job import Job
    from app.models.student import Student
    from app.schemas.common import Region

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 0, "PREPARING", "학생 식별 OCR을 준비 중입니다.")
        db.commit()

        exam = db.get(Exam, job.exam_id)
        if not exam.student_name_region or not exam.student_no_region:
            raise ValueError("학생 식별 영역이 지정되지 않았습니다.")

        name_region = Region(**exam.student_name_region)
        no_region = Region(**exam.student_no_region)
        answer_sheet_ids = (job.input_json or {}).get("answer_sheet_ids")
        sheet_filter = [
            AnswerSheet.exam_id == exam.exam_id,
            AnswerSheet.status == SheetStatus.UNMATCHED,
        ]
        if answer_sheet_ids:
            sheet_filter.append(AnswerSheet.answer_sheet_id.in_(answer_sheet_ids))

        sheets = (
            db.query(AnswerSheet)
            .filter(*sheet_filter)
            .order_by(AnswerSheet.answer_sheet_id)
            .all()
        )

        total = len(sheets)
        storage = get_storage()
        ocr_client = ClovaOcrClient()
        matched = 0
        failed = 0
        failed_targets: list[dict] = []

        job.progress_json = _build_progress(0, total, "OCR", "학생 식별 OCR을 시작합니다.")
        db.commit()

        for index, sheet in enumerate(sheets, start=1):
            pdf_bytes = storage.download(sheet.file_key)
            name_img = crop_region(pdf_bytes, name_region.page, name_region.x, name_region.y, name_region.w, name_region.h)
            no_img = crop_region(pdf_bytes, no_region.page, no_region.x, no_region.y, no_region.w, no_region.h)

            ocr_name = _normalize_name(ocr_client.recognize(name_img))
            ocr_no = _normalize_student_no(ocr_client.recognize(no_img))

            if not ocr_no:
                failed += 1
                failed_targets.append(
                    {
                        "answerSheetId": sheet.answer_sheet_id,
                        "reason": "STUDENT_NO_EMPTY",
                        "ocrName": ocr_name,
                    }
                )
            else:
                student = (
                    db.query(Student)
                    .filter(Student.exam_id == exam.exam_id, Student.student_no == ocr_no)
                    .first()
                )

                if student is None:
                    student = Student(
                        exam_id=exam.exam_id,
                        name=ocr_name or ocr_no,
                        student_no=ocr_no,
                    )
                    db.add(student)
                    db.flush()
                elif ocr_name and student.name != ocr_name:
                    student.name = ocr_name

                duplicate_sheet = (
                    db.query(AnswerSheet)
                    .filter(
                        AnswerSheet.exam_id == exam.exam_id,
                        AnswerSheet.student_id == student.student_id,
                        AnswerSheet.answer_sheet_id != sheet.answer_sheet_id,
                    )
                    .first()
                )
                if duplicate_sheet:
                    failed += 1
                    failed_targets.append(
                        {
                            "answerSheetId": sheet.answer_sheet_id,
                            "reason": "DUPLICATE_STUDENT_ID",
                            "ocrName": ocr_name,
                        }
                    )
                else:
                    sheet.student_id = student.student_id
                    sheet.status = SheetStatus.MATCHED
                    matched += 1

            if index % max(1, total // 10) == 0 or index == total:
                job.progress_json = _build_progress(index, total, "OCR", f"{index}/{total} 답안지의 학생 정보를 인식 중입니다.")
                db.commit()

        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": total, "succeeded": matched, "failed": failed},
            "resultRef": {"type": "answer_sheets", "examId": exam.exam_id},
            "warnings": [
                {
                    "code": "UNMATCHED_STUDENT_ID",
                    "message": "일부 답안지에서 학번 인식에 실패했습니다.",
                }
            ] if failed_targets else [],
        }
        if failed_targets:
            job.status = JobStatus.FAILED
            job.progress_json = _build_progress(total, total, "FAILED", "일부 답안지의 학생 식별에 실패했습니다.")
            job.error_json = {
                "code": "PARTIAL_STUDENT_ID_RECOGNITION_FAILED",
                "message": "일부 답안지의 학생 식별에 실패했습니다.",
                "retryable": False,
                "category": "validation",
                "failedTargets": failed_targets,
            }
        else:
            job.status = JobStatus.DONE
            job.progress_json = _build_progress(total, total, "DONE", "학생 식별 OCR이 완료되었습니다.")
        db.commit()

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        db.rollback()
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "학생 식별 OCR에 실패했습니다.")
        job.error_json = {
            "code": "INTERNAL",
            "message": str(e),
            "retryable": False,
            "category": "internal",
        }
        db.commit()

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_answer_ocr(self, job_id: int):
    import app.db.models  # noqa: F401
    from app.db.session import SessionLocal
    from app.enums.job_status import JobStatus
    from app.enums.ocr_status import OCRStatus
    from app.enums.layout_mode import LayoutMode
    from app.enums.problem_type import ProblemType
    from app.infrastructure.ocr.base import OcrClient
    from app.infrastructure.ocr.deps import get_ocr_client
    from app.infrastructure.pdf.renderer import crop_region
    from app.infrastructure.storage.deps import get_storage
    from app.models.answer_region import AnswerRegion
    from app.models.answer_sheet import AnswerSheet
    from app.models.exam import Exam
    from app.models.job import Job
    from app.models.ocr_result import OCRResult
    from app.models.problem import Problem
    from app.schemas.common import Region

    db = SessionLocal()
    job = db.get(Job, job_id)
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        job.progress_json = _build_progress(0, 0, "PREPARING", "답안 OCR을 준비 중입니다.")
        db.commit()

        exam = db.get(Exam, job.exam_id)
        scope = job.input_json or {}
        scope_layout_mode = ((scope.get("scope") or {}).get("layoutMode"))
        layout_mode = LayoutMode(scope_layout_mode) if scope_layout_mode else exam.layout_mode
        sheet_filter = [
            AnswerSheet.exam_id == exam.exam_id,
            AnswerSheet.student_id.isnot(None),
        ]
        if job.answer_sheet_id is not None:
            sheet_filter.append(AnswerSheet.answer_sheet_id == job.answer_sheet_id)
        sheets = (
            db.query(AnswerSheet)
            .filter(*sheet_filter)
            .order_by(AnswerSheet.answer_sheet_id)
            .all()
        )

        # (sheet, region) 쌍 목록 구성 — sheet 순서대로 묶여 있어 PDF 캐시 가능
        targets: list[tuple[AnswerSheet, AnswerRegion]] = []
        for sheet in sheets:
            regions = (
                db.query(AnswerRegion)
                .filter(
                    AnswerRegion.answer_sheet_id == sheet.answer_sheet_id,
                    AnswerRegion.layout_mode == layout_mode,
                )
                .all()
            )
            for region in regions:
                targets.append((sheet, region))

        problem_ids = list({region.problem_id for _, region in targets})
        problem_map = {p.problem_id: p for p in db.query(Problem).filter(Problem.problem_id.in_(problem_ids)).all()}

        total = len(targets)
        if total == 0:
            job.status = JobStatus.DONE
            job.completed_at = datetime.now(timezone.utc)
            job.progress_json = _build_progress(0, 0, "DONE", "처리할 답안 영역이 없습니다.")
            job.result_json = {"summary": {"processed": 0, "succeeded": 0, "failed": 0}}
            db.commit()
            return

        storage = get_storage()
        ocr_clients: dict[ProblemType, OcrClient] = {}
        succeeded = 0
        failed = 0
        failed_targets: list[dict] = []

        # 같은 sheet가 연속으로 나오므로 교체 시점에만 재다운로드
        current_sheet_id: int | None = None
        current_pdf_bytes: bytes | None = None

        job.progress_json = _build_progress(0, total, "OCR", "답안 OCR을 시작합니다.")
        db.commit()

        for index, (sheet, region) in enumerate(targets, start=1):
            try:
                ocr_result = (
                    db.query(OCRResult)
                    .filter(OCRResult.answer_region_id == region.answer_region_id)
                    .first()
                )
                if ocr_result and ocr_result.updated_at >= region.region_updated_at:
                    succeeded += 1
                    continue

                if sheet.answer_sheet_id != current_sheet_id:
                    current_sheet_id = sheet.answer_sheet_id
                    current_pdf_bytes = storage.download(sheet.file_key)

                if not region.bbox_region:
                    raise ValueError("bbox_region이 지정되지 않았습니다.")

                problem_type = problem_map[region.problem_id].type
                if problem_type not in ocr_clients:
                    ocr_clients[problem_type] = get_ocr_client(problem_type)

                r = Region(**region.bbox_region)
                image_bytes = crop_region(current_pdf_bytes, r.page, r.x, r.y, r.w, r.h)
                ocr_text = ocr_clients[problem_type].recognize(image_bytes)

                if problem_type == ProblemType.MULTIPLE_CHOICE:
                    marked_choice = _parse_marked_choice(ocr_text)
                    text = None
                else:
                    marked_choice = None
                    text = ocr_text

                now = datetime.now(timezone.utc)
                if ocr_result:
                    ocr_result.text = text
                    ocr_result.marked_choice = marked_choice
                    ocr_result.status = OCRStatus.RAW
                    ocr_result.updated_at = now
                else:
                    db.add(OCRResult(
                        answer_region_id=region.answer_region_id,
                        text=text,
                        marked_choice=marked_choice,
                        status=OCRStatus.RAW,
                        updated_at=now,
                    ))

                succeeded += 1

            except requests.exceptions.RequestException:
                raise  # 외부 except로 전파 → self.retry() 호출

            except Exception as e:
                failed += 1
                failed_targets.append({
                    "answerRegionId": region.answer_region_id,
                    "answerSheetId": sheet.answer_sheet_id,
                    "reason": str(e),
                })

            if index % max(1, total // 10) == 0 or index == total:
                job.progress_json = _build_progress(index, total, "OCR", f"{index}/{total} 답안 영역을 인식 중입니다.")
                db.commit()

        job.completed_at = datetime.now(timezone.utc)
        job.result_json = {
            "summary": {"processed": total, "succeeded": succeeded, "failed": failed},
            "resultRef": {"type": "ocr_results", "examId": exam.exam_id},
        }

        if failed > 0:
            job.status = JobStatus.FAILED
            job.progress_json = _build_progress(total, total, "FAILED", "일부 답안 영역의 OCR에 실패했습니다.")
            job.error_json = {
                "code": "PARTIAL_OCR_FAILED",
                "message": "일부 답안 영역의 OCR에 실패했습니다.",
                "retryable": False,
                "category": "provider",
                "failedTargets": {"answerRegionIds": [t["answerRegionId"] for t in failed_targets]},
            }
        else:
            job.status = JobStatus.DONE
            job.progress_json = _build_progress(total, total, "DONE", "답안 OCR이 완료되었습니다.")

        db.commit()

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    except Exception as e:
        db.rollback()
        job.status = JobStatus.FAILED
        job.progress_json = _build_progress(0, 0, "FAILED", "답안 OCR에 실패했습니다.")
        job.error_json = {
            "code": "INTERNAL",
            "message": str(e),
            "retryable": False,
            "category": "internal",
        }
        db.commit()

    finally:
        db.close()


def _normalize_name(raw: str) -> str:
    return " ".join(raw.split()).strip()


def _normalize_student_no(raw: str) -> str:
    return "".join(ch for ch in raw if ch.isdigit())


def _parse_marked_choice(raw: str) -> int | None:
    digits = [ch for ch in raw if ch.isdigit()]
    return int(digits[0]) if len(digits) == 1 else None
