from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import user  # noqa: F401  # 모델 import로 metadata 등록
from app.services.user_service import ensure_initial_admin


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:  # type: Session
        ensure_initial_admin(db)
