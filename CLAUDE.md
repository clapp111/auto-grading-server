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

## 인증

- JWT Bearer 토큰 인증. `app/core/security.py`의 `get_current_member` DI로 `Member` 주입
- 라우터는 `current_member: Member = Depends(get_current_member)`를 받고, Service에는 `current_member.member_id`만 전달
- 라우터에서 토큰 파싱/사용자 조회 금지 — 반드시 `get_current_member` DI 사용
- 토큰 발급: `create_access_token({"sub": str(member_id)})`, 비밀번호는 `hash_password`/`verify_password`(bcrypt)
- 인증 실패는 `UnauthorizedException` (401). 인라인 401 raise 금지

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

## 소유권 / 접근 권한 검증

- Service에서 리소스 조회 후 `member_id` 비교로 접근 권한 확인
- 리소스 미존재 / 권한 불일치 모두 같은 NotFoundError 반환 (존재 여부 노출 금지)

```python
exam = self.repo.get_by_id(exam_id)
if not exam or exam.member_id != member_id:
    raise ExamNotFoundError()
```

### 협업(공유) 접근 — exam_member

시험은 소유자 외에 **초대를 수락한 참여자**(`exam_member` 테이블)도 접근할 수 있다. `ExamRepository`에 두 종류의 조회를 구분한다:

- `get_accessible(exam_id, member_id)` — 소유자 **또는** 참여자 (읽기/일반 작업용). `EXISTS` 서브쿼리로 조회(참여자 다수 시 join 행 중복 방지)
- `get_owned(exam_id, member_id)` — 소유자 **전용** (초대 관리·삭제 등 소유자 한정 동작)

권한 부족 시 반환할 예외 구분:
- 무관한 사용자: 시험 존재를 숨김 → `ExamNotFoundError` (404)
- 참여자가 소유자 전용 동작 시도: `ExamOwnerRequiredError` (403)

---

## SQLAlchemy 모델

- 모델은 `app/models/` 아래 도메인별 개별 파일. `app/db/models.py`가 모든 모델을 일괄 import하여 Alembic autogenerate·SQLAlchemy 레지스트리에 등록 (새 모델 추가 시 여기에도 등록 필수)
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
- `ExamStep`은 진행 단계(0~7)를 나타내는 `IntEnum`. 순서 비교가 필요하므로 `str, Enum`이 아닌 `IntEnum` 사용
- 기존 Enum 목록:
  - `ExamStatus`: DRAFT, SETUP, OCR, GRADING, DONE
  - `ExamStep` (IntEnum): DRAFT(0), PROBLEM_SETUP(1), RUBRIC(2), ANSWER_UPLOAD(3), REGION_SETUP(4), OCR(5), GRADING(6), DONE(7)
  - `JobStatus`: PENDING, RUNNING, DONE, FAILED, CANCELED
  - `JobType`: PROBLEM_OCR, MODEL_ANSWER_OCR, RUBRIC_SUGGEST, ANSWER_SHEET_RECOGNIZE, REGION_TEMPLATE_APPLY, ANSWER_OCR_RUN, AUTO_GRADE, LLM_GRADE, EXPORT_CSV
  - `ProblemType`: MULTIPLE_CHOICE, SHORT_ANSWER, DESCRIPTIVE, CODING
  - `ProgrammingLanguage`: CPP, JAVA, PYTHON, C
  - `LayoutMode`: FIXED, FREE
  - `GradeMethod`: AUTO, LLM, HUMAN
  - `GradeStatus`: CONFIRMED, SUGGESTED
  - `RubricSource`: LLM, HUMAN
  - `OCRStatus`: RAW, REVIEWED
  - `SheetStatus`: MATCHED, UNMATCHED
  - `RegionShape`: RECT, LASSO
  - `Role`: ADMIN, NORMAL (계정 권한)
  - `AffiliationRole`: PROFESSOR, TEACHER, TUTOR, TA (소속 직함)
  - `InvitationStatus`: PENDING, ACCEPTED, DECLINED, CANCELED

---

## 코드 품질

- 함수/변수명은 영어 snake_case, 클래스명은 PascalCase
- **인라인 주석**(`#`)은 WHY가 비자명할 때만. 무엇을 하는지 설명하는 주석 금지 (서비스 메서드 docstring은 예외 — 아래 규약 참고)
- `request.model_dump(exclude_unset=True)` — PATCH 요청 시 미전송 필드 제외
- `model_validate(obj)` — ORM 모델 → Schema 변환 시 사용
- 새 예외 클래스를 추가하면 반드시 `main.py`에 handler도 등록

---

## Docstring 규약 (서비스 · 워커 레이어)

서비스 레이어(`app/services/*.py`)와 Celery 워커(`app/workers/*.py`)에 적용하는 docstring 규약. **Google 스타일**(`Args:`/`Returns:`/`Raises:`)을 사용한다. 인라인 주석의 "WHY-only" 규칙과 별개로, 이 docstring은 **무엇을 하는지 서술하는 필수 문서 계층**이다.

### 적용 범위 (레이어별)

| 레이어 | 규약 |
|---|---|
| 서비스 (`app/services/`) | 풀 규약 (필수) |
| Celery 워커 (`app/workers/`) | 풀 규약 (필수) |
| 엔드포인트 (`app/api/`) | 생략 |
| 리포지토리 (`app/repositories/`) | docstring 생략. 비자명한 쿼리는 인라인 `#` WHY 주석 |
| 스키마·모델·Enum | 생략 |

### 작성 대상

| 대상 | 작성 여부 |
|---|---|
| 서비스 메서드 (public / `_`-prefixed private) | **필수** |
| Celery task 함수 (`@celery_app.task`) 및 워커 헬퍼 함수 | **필수** |
| 클래스 레벨 | 생략 |
| 모듈 하단 `get_*_service` DI 팩토리 | 생략 |
| Pydantic schema·record 성격 내부 타입 | 생략 |

### 메서드 영역 구분

서비스 메서드는 역할에 따라 `주요 서비스 기능`과 `헬퍼 함수` 영역으로 구분한다. 접근 제어자나 트랜잭션 유무가 아니라 **서비스 로직에서의 중요도**로 판단한다.

| 영역 | 분류 기준 |
|---|---|
| 주요 서비스 기능 | 핵심 비즈니스 흐름을 수행하거나 서비스 로직상 중요한 메서드 |
| 헬퍼 함수 | 반복 코드를 줄이는 보조 메서드 또는 단순·부수적 메서드 (예: `_get_exam_or_raise`) |

- 배치 순서: **주요 서비스 기능 먼저 → 헬퍼 함수 나중**. 필요 시 메서드를 영역에 맞게 재배치한다
- 메서드가 **하나뿐인** 서비스는 배너를 생략한다 (메서드 2개 이상부터 표시)

영역은 다음 형식으로 표시한다.

```python
    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================
```

### 요약 문장 (첫 줄)

- 한국어, 서술어로 끝나는 **단문** 한 줄. 마침표로 종결
- 주어 생략 (메서드 시그니처에 이미 있음)
- 여는 `"""` 바로 뒤 같은 줄에 작성

```python
# 좋은 예
"""투표에 등록된 모든 참여자를 삭제한다."""

# 나쁜 예 — 주어 중복
"""이 메서드는 투표에 등록된 모든 참여자를 삭제합니다."""
```

### 보충 설명

비즈니스 규칙, 제약 조건, 비자명한 동작이 있을 때만 요약 문장 다음 빈 줄을 두고 추가한다.

```python
"""투표 참여자의 참석 가능한 시간 슬롯을 갱신한다.

기존 참석 가능 기록을 모두 삭제한 후 요청된 시간 슬롯으로 다시 저장한다.
"""
```

### Args

- 모든 파라미터에 작성 (`self` 제외). 마침표 없음
- 파라미터가 **무엇인지** 서술 (용도가 아닌 의미). 타입은 시그니처에 있으므로 반복 금지

```python
# 좋은 예
Args:
    vote: 참여자를 등록할 투표
    team_member_ids: 투표 대상으로 지정할 팀 멤버 ID 목록

# 나쁜 예 — 타입 반복
Args:
    vote: Vote 엔티티
```

### Returns

- 마침표 없음. 반환값이 `None`이면 `Returns` 생략
- `bool` 반환은 아래 형식 고정 (Python 리터럴은 `` `True` ``/`` `False` ``)

```python
# 일반
Returns:
    날짜 오름차순으로 정렬된 후보 날짜 목록

# bool 고정 형식
Returns:
    투표 대상자이면 `True`, 그렇지 않으면 `False`
```

### Raises

- `app/core/exceptions.py`에 정의된 **도메인 예외**(`*Error`)만 문서화 (Java의 `RestApiException`에 대응)
- 예외별로 한 줄. 발생 조건을 마침표 없이 서술

```python
Raises:
    ExamNotFoundError: 시험을 찾을 수 없거나 접근 권한이 없는 경우
    ExamOwnerRequiredError: 시험 소유자가 아닌 경우
```

### 인라인 참조

| 표기 | 사용 시점 | 예 |
|---|---|---|
| `` `값` `` (백틱) | 리터럴 값·파라미터명 참조 | `` `True` ``, `` `None` `` |
| `` `타입.상수` `` | 다른 타입·Enum 상수 참조 | `` `GradeStatus.CONFIRMED` ``, `` `ExamStep.OCR` `` |

### 섹션 순서

```
요약 문장

보충 설명   ← 필요한 경우만

Args:
Returns:
Raises:
```

### 작성하지 않는 것

- 버전/작성자 메타 — 이력은 Git으로 관리
- 코드·메서드명·파라미터명을 그대로 반복하는 서술

### 종합 예시 — 서비스

```python
def create_invitation(self, exam_id: int, member_id: int, request: InvitationCreateRequest) -> ExamInvitationResponse:
    """시험에 참여자를 초대한다.

    소유자만 초대할 수 있으며, 이미 참여 중이거나 대기 중인 초대가 있으면 거부한다.

    Args:
        exam_id: 초대를 생성할 시험 ID
        member_id: 초대를 요청한 사용자(소유자) ID
        request: 초대할 대상의 이메일을 담은 요청

    Returns:
        생성된 초대 정보

    Raises:
        ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        ExamOwnerRequiredError: 시험 소유자가 아닌 경우
        MemberNotFoundError: 초대 대상 이메일의 사용자가 없는 경우
        SelfInvitationError: 자기 자신을 초대한 경우
        AlreadyExamMemberError: 이미 참여 중인 사용자인 경우
        InvitationAlreadyPendingError: 이미 대기 중인 초대가 있는 경우
    """
```

### 워커(Celery task) 적용 시 차이

Celery task도 풀 규약을 따르되, 형태 차이로 인해 아래를 조정한다.

- task는 모듈 레벨 함수이므로 `self`(Celery bind)는 `Args`에 적지 않는다
- 대부분 DB 부수효과만 내고 값을 반환하지 않으므로 `Returns`는 보통 생략. 반환하면 그때만 작성
- `Raises`에는 실제 전파되는 예외만 서술한다. task가 예외를 삼켜 FAILED로 기록하는 경우는 생략하고, `self.retry`로 재전파되는 예외(예: `RequestException`)만 명시한다
- 보충 설명에는 잡 상태 흐름(`RUNNING → DONE/FAILED`)·재시도·부분 실패 처리 등 비자명한 동작을 적는다
- 영역 구분 배너도 사용하되 라벨은 `주요 워커 기능`/`헬퍼 함수`로 한다. task 함수를 `주요 워커 기능`, 그 외 보조 함수를 `헬퍼 함수`로 묶으며, task가 하나뿐이고 헬퍼가 없는 파일(예: `region_tasks.py`)은 배너를 생략한다 (모듈 레벨이므로 들여쓰기 없이 표기)

### 종합 예시 — 워커

```python
@celery_app.task(bind=True, max_retries=3)
def run_problem_ocr(self, job_id: int):
    """문제 이미지 영역을 OCR하여 결과를 저장한다.

    잡을 RUNNING으로 전환한 뒤 문제 영역을 잘라 OCR을 수행하고, 성공 시 DONE으로 마감한다.
    외부 OCR 호출 실패는 지수 백오프로 재시도하며, 그 외 오류는 FAILED로 기록한다.

    Args:
        job_id: 처리할 OCR 잡 ID

    Raises:
        RequestException: 외부 OCR API 호출이 실패해 재시도가 필요한 경우
    """
```
