# 비동기 작업 (Celery Worker)

## Celery Worker

- task는 도메인별 파일로 분리: `app/workers/ocr_tasks.py`, `rubric_tasks.py`, `grade_tasks.py`, `region_tasks.py`. 공용 유틸은 `app/workers/utils.py` (`_build_progress` 등), Celery 앱 설정은 `tasks.py`

### Job 상태 흐름

```
PENDING → RUNNING → DONE
                  → FAILED
```

- task 시작 즉시: `status = RUNNING`, `started_at` 설정 후 commit
- task 완료: `status = DONE`, `completed_at` 설정 후 commit
- 실패: `db.rollback()` 후 `status = FAILED`, `error_json` 설정 후 commit
- `finally` 블록에서 반드시 `db.close()`

### progress_json

- `_build_progress(current, total, stage, message)` 유틸 사용
- 10% 단위 또는 전체 항목 처리 완료 시점에만 commit
- 매 항목마다 commit 금지 (성능 저하)

```python
if index % max(1, (total + 9) // 10) == 0 or index == total:
    job.progress_json = _build_progress(index, total, "OCR", f"{index}/{total} 처리 중")
    db.commit()
```

### 에러 처리 계층

```python
except requests.exceptions.RequestException as e:
    raise self.retry(exc=e, countdown=2 ** self.request.retries)  # 지수 백오프

except Exception as e:
    db.rollback()
    job.status = JobStatus.FAILED
    job.error_json = {"code": "INTERNAL", "message": str(e), "retryable": False, ...}
    db.commit()
```

- 외부 API 실패(`RequestException`): `max_retries=3`, 지수 백오프 retry
- 내부 오류: FAILED 처리 후 종료 (`retryable: false`)
- 부분 실패(배치): `failedTargets` 목록 기록

### error_json 구조

```json
{
  "code": "ERROR_CODE",
  "message": "설명",
  "retryable": false,
  "category": "internal | validation | provider",
  "failedTargets": []
}
```

### result_json 구조

```json
{
  "summary": {"processed": N, "succeeded": N, "failed": N},
  "resultRef": {"type": "resource_type", "examId": N},
  "warnings": []
}
```

### Celery task 내 import

- task 함수 내부에서 지연 import 사용 (순환 참조 방지)
- `import app.db.models  # noqa: F401` 라인으로 모든 모델을 SQLAlchemy 레지스트리에 등록

## 비동기 Job 생성 패턴

1. `idempotency_key` 체크 (중복 요청 방지)
2. Job 레코드 생성 (`status=PENDING`)
3. Celery task 호출 (`.delay(job_id)`)
4. `202 + JobStartedResponse(job_id, status)` 반환