# Controller (Router)

## 레이어 분리

- **Router → Service → Repository** 단방향 흐름만 허용
- 라우터는 요청 수신 + `ApiResponse` 래핑만 담당. **DB 직접 접근 및 비즈니스 로직 금지**
- Service에는 필요한 값만 전달하고, 응답은 Service가 반환한 schema를 `ApiResponse`로 감싸 반환

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