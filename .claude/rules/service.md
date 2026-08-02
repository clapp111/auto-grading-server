# Service

## 레이어 분리

- **Router → Service → Repository** 단방향 흐름만 허용
- Service는 비즈니스 로직 수행, Repository 호출, schema 변환(`model_validate`)을 담당
- 레이어 **역방향 참조 금지** (예: Repository가 Service 호출)

## 의존성 주입

- Service는 클래스로 작성하고 `__init__`에서 Repository를 받는다
- 모듈 하단 `get_*_service` 팩토리에서 FastAPI `Depends(get_db)`로 세션을 받아 주입한다

```python
class ExamService:
    def __init__(self, repo: ExamRepository):
        self.repo = repo

def get_exam_service(db: Session = Depends(get_db)) -> ExamService:
    return ExamService(ExamRepository(db))
```

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

## 파일 업로드 — Presigned URL 패턴

- 파일은 서버를 경유하지 않고 **클라이언트가 S3에 직접 업로드**한다
- 순서: `file_key` 생성 → DB에 `file_key` 저장 → Presigned URL 발급 → 클라이언트가 S3 직접 업로드
- DB 저장을 먼저 하므로 업로드 실패 시 미사용 key가 남을 수 있다. **파일을 실제 사용하는 시점에 S3 존재 여부를 검증**한다
- Request/Response DTO는 `schemas/s3.py`의 `PresignedUrlRequest` / `PresignedUrlResponse` 사용

```python
def issue_problem_sheet_url(exam_id: int, request: PresignedUrlRequest) -> PresignedUrlResponse:
    exam = self.repo.get_by_id(exam_id)
    file_key = self.storage.generate_key(f"exams/{exam_id}/problem-sheet", request.file_name)
    self.repo.update(exam, problem_sheet_file_key=file_key)  # DB 먼저 저장
    upload_url = self.storage.generate_presigned_url(file_key, request.content_type)
    return PresignedUrlResponse(upload_url=upload_url, file_key=file_key)
```