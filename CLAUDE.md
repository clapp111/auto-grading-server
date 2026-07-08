# Auto Grading Server — Code Review Rules

## 프로젝트 개요

FastAPI + SQLAlchemy + Celery 기반 자동 채점 서버. OCR·LLM을 이용해 시험지를 0~7단계로 채점하는 파이프라인.

---

## 레이어 분리

- **Router** → **Service** → **Repository** 단방향 흐름만 허용
- 라우터: 요청 수신 + `ApiResponse` 래핑만. DB 직접 접근 및 비즈니스 로직 금지
- Service: 비즈니스 로직, repo 호출, schema 변환(`model_validate`)
- Repository: DB 쿼리만. 비즈니스 판단 금지
- 레이어 역방향 참조(예: repo가 service 호출) 금지

## 응답 형식

- 모든 엔드포인트 응답은 `ApiResponse[T]` (`app/schemas/common.py`) 래퍼로 반환
- 비동기 작업 시작 엔드포인트: `status_code=202`, `ApiResponse[JobStartedResponse]` 반환
- 삭제 엔드포인트: `status_code=204`, `Response(status_code=204)` 반환
- 오류 응답: `ApiResponse(error=ApiError(code=..., message=...))` 구조

## 엔드포인트 네이밍

| 패턴 | 함수명 예시 |
|---|---|
| 단건 조회 | `get_exam`, `get_job` |
| 목록 조회 | `list_exams`, `list_students` |
| 생성 | `create_exam`, `create_problem` |
| 수정 | `update_exam`, `update_rubric` |
| 삭제 | `delete_exam` |

## Schema 네이밍

| 용도 | 클래스명 |
|---|---|
| 생성 요청 | `{Resource}CreateRequest` |
| 수정 요청 | `{Resource}UpdateRequest` |
| 단건 응답 | `{Resource}Response` |
| 목록 응답 | `{Resource}ListResponse` |
| 비동기 응답 | `JobStartedResponse` |

- 페이지네이션 메타는 `PageMeta` / `SliceMeta` / `OffsetMeta` / `CursorMeta` 중 적합한 것 사용
- Schema에는 `model_config = {"from_attributes": True}` 필요 시 명시

## 예외 처리

- 비즈니스 예외는 반드시 `app/core/exceptions.py`에 정의 (예: `ExamNotFoundError`)
- `app/main.py`의 `exception_handler`로 HTTP 상태 코드와 에러 코드 매핑
- 인라인 `HTTPException` raise 금지 — 도메인 예외만 사용
- 새 예외 추가 시 `exceptions.py` 정의 + `main.py` 핸들러 등록 두 가지 모두 필요

## 소유권 검증

- Service에서 리소스 조회 후 `member_id` 비교로 소유권 확인
- 리소스 미존재 / 소유권 불일치 모두 같은 NotFoundError 반환 (존재 여부 노출 금지)

```python
exam = self.repo.get_by_id(exam_id)
if not exam or exam.member_id != member_id:
    raise ExamNotFoundError()
```

---

## SQLAlchemy 모델

- Enum 컬럼: `SAEnum(EnumClass)` 사용
- JSON 컬럼: `_json` suffix (input_json, result_json 등)
- PK 컬럼: `{tablename}_id` (exam_id, problem_id 등)
- `Mapped` + `mapped_column` 스타일 (구버전 `Column` 사용 금지)
- 순환 참조 방지: `from __future__ import annotations` + `TYPE_CHECKING` 블록
- N+1 방지: `selectinload` 또는 `joinedload` 명시. 루프 내 단건 쿼리 금지

### JSON 필드 직렬화 패턴

```python
# 저장
problem.region = data.region.model_dump() if data.region else None

# 복원
region = Region(**problem.region) if problem.region else None
```

## Repository 패턴

- `get_by_id(id)` → `Model | None`
- `list_by_{criteria}(...)` → `list[Model]`
- `create(...)` → `Model` (commit + refresh 포함)
- `update(model, **kwargs)` → `Model` (setattr 루프 + commit + refresh)
- `delete(id)` → `None` (execute delete + commit)
- Repository는 단일 세션(`self.db`) 사용. 세션 생성/종료는 DI(FastAPI `Depends`)가 담당

---

## Celery Worker

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
if index % max(1, total // 10) == 0 or index == total:
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

---

## 파일 업로드 (Presigned URL 패턴)

1. `file_key` 생성
2. DB에 `file_key` 먼저 저장
3. Presigned URL 생성 후 클라이언트에 반환
4. 실제 사용 시점에 S3 존재 여부 검증

`StorageClient`는 `app/infrastructure/storage/deps.py`의 `get_storage()` DI를 통해 주입.

---

## 비동기 Job 생성 패턴

1. `idempotency_key` 체크 (중복 요청 방지)
2. Job 레코드 생성 (`status=PENDING`)
3. Celery task 호출 (`.delay(job_id)`)
4. `202 + JobStartedResponse(job_id, status)` 반환

---

## Enum

- 새 Enum은 `app/enums/` 에 별도 파일로 추가
- SQLAlchemy에서 `SAEnum(EnumClass)` 형태로 사용
- 기존 Enum 목록:
  - `ExamStatus`: DRAFT, SETUP, OCR, GRADING, DONE
  - `JobStatus`: PENDING, RUNNING, DONE, FAILED, CANCELED
  - `JobType`: MODEL_ANSWER_OCR, RUBRIC_SUGGEST, ANSWER_SHEET_RECOGNIZE, REGION_TEMPLATE_APPLY, ANSWER_OCR_RUN, AUTO_GRADE, LLM_GRADE, EXPORT_CSV
  - `ProblemType`: MULTIPLE_CHOICE, SHORT_ANSWER, DESCRIPTIVE, CODING
  - `LayoutMode`: FIXED, FREE
  - `GradeMethod`: AUTO, LLM, HUMAN
  - `GradeStatus`: CONFIRMED, SUGGESTED
  - `OCRStatus`: RAW, REVIEWED
  - `SheetStatus`: MATCHED, UNMATCHED
  - `RegionShape`: RECT, LASSO

---

## 코드 품질

- 함수/변수명은 영어 snake_case, 클래스명은 PascalCase
- 주석은 WHY가 비자명할 때만. 무엇을 하는지 설명하는 주석 금지
- `request.model_dump(exclude_unset=True)` — PATCH 요청 시 미전송 필드 제외
- `model_validate(obj)` — ORM 모델 → Schema 변환 시 사용
- 새 예외 클래스를 추가하면 반드시 `main.py`에 handler도 등록
