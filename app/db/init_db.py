from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    # 개발 환경 전용 — 운영에서는 alembic upgrade head 사용
    Base.metadata.create_all(bind=engine)
