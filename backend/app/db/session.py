from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _create_engine(database_url: str):
    if database_url.startswith("sqlite:///"):
        db_file = database_url.replace("sqlite:///", "", 1)
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url)


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
