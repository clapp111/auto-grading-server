# 코드 품질 (Quality Assurance)

## 포맷터 · 린터

- 코드 포맷터는 **black**, 린터는 **ruff** 를 사용한다
- 커밋 전 `black`으로 포맷팅하고 `ruff`로 린트 검사를 통과시킨다

## 코드 품질

- 함수/변수명은 영어 snake_case, 클래스명은 PascalCase
- **인라인 주석**(`#`)은 WHY가 비자명할 때만. 무엇을 하는지 설명하는 주석 금지 (서비스 메서드 docstring은 예외 — 아래 규약 참고)
- `request.model_dump(exclude_unset=True)` — PATCH 요청 시 미전송 필드 제외
- `model_validate(obj)` — ORM 모델 → Schema 변환 시 사용
- 새 예외 클래스를 추가하면 반드시 `main.py`에 handler도 등록 (상세는 `service.md` 참고)

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
def create_invitation(
    self, exam_id: int, member_id: int, request: InvitationCreateRequest
) -> ExamInvitationResponse:
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
