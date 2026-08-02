# DTO (Schema)

## 파일 분리 원칙

- 도메인마다 `Request` / `Response` 스키마를 같은 파일에 둔다 (예: `schemas/exam.py`)
- 여러 도메인 공통 타입은 `schemas/common.py`에 정의 (`Region`, `Point`, `ApiResponse`, 기반 Meta 등)
- **도메인 전용 Meta 타입은 `common.py`의 기반 Meta를 상속해 해당 도메인 스키마 파일에 정의**한다

```python
# schemas/exam.py
from app.schemas.common import CursorMeta

class ExamCursorMeta(CursorMeta):
    draft: int
    in_progress: int
    done: int
```

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