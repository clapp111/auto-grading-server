# Repository 패턴

## 레이어 분리

- **Router → Service → Repository** 단방향 흐름만 허용
- Repository는 DB 쿼리만 담당. **비즈니스 판단 금지**
- 레이어 **역방향 참조 금지** (Repository가 Service를 호출하지 않음)

## Repository 메서드

- `get_by_id(id)` → `Model | None`
- `list_by_{criteria}(...)` → `list[Model]`
- `create(...)` → `Model` (commit + refresh 포함)
- `update(model, **kwargs)` → `Model` (setattr 루프 + commit + refresh)
- `delete(id)` → `None` (execute delete + commit)
- Repository는 단일 세션(`self.db`) 사용. 세션 생성/종료는 DI(FastAPI `Depends`)가 담당
