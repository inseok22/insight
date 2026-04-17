from sqlalchemy.orm import Session

from app.db.base import AdminBase, UserBase
from app.db.session import AdminSessionLocal, admin_engine, user_engine
from app.models import admin, user  # noqa: F401  # 모델 import로 metadata 등록
from app.services.admin_service import ensure_initial_admin


def init_db() -> None:
    AdminBase.metadata.create_all(bind=admin_engine)
    UserBase.metadata.create_all(bind=user_engine)
    with AdminSessionLocal() as db:  # type: Session
        ensure_initial_admin(db)
