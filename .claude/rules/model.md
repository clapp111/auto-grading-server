# SQLAlchemy 모델

- 모델은 `app/models/` 아래 도메인별 개별 파일. `app/db/models.py`가 모든 모델을 일괄 import하여 Alembic autogenerate·SQLAlchemy 레지스트리에 등록 (새 모델 추가 시 여기에도 등록 필수)
- Enum 컬럼: `SAEnum(EnumClass)` 사용
- JSON 컬럼: `_json` suffix (input_json, result_json 등)
- PK 컬럼: `{tablename}_id` (exam_id, problem_id 등)
- `Mapped` + `mapped_column` 스타일 (구버전 `Column` 사용 금지)
- 순환 참조 방지: `from __future__ import annotations` + `TYPE_CHECKING` 블록
- N+1 방지: `selectinload` 또는 `joinedload` 명시. 루프 내 단건 쿼리 금지

## JSON 필드 직렬화 패턴

```python
# 저장
problem.region = data.region.model_dump() if data.region else None

# 복원
region = Region(**problem.region) if problem.region else None
```
