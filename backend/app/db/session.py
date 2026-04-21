from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _create_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, pool_recycle=3600)


admin_engine = _create_engine(settings.admin_database_url)
user_engine = _create_engine(settings.user_database_url)

AdminSessionLocal = sessionmaker(bind=admin_engine, autoflush=False, autocommit=False, class_=Session)
UserSessionLocal = sessionmaker(bind=user_engine, autoflush=False, autocommit=False, class_=Session)


def get_admin_db() -> Generator[Session, None, None]:
    db = AdminSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_db() -> Generator[Session, None, None]:
    db = UserSessionLocal()
    try:
        yield db
    finally:
        db.close()
