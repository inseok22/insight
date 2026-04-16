from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

if settings.database_url.startswith("sqlite:///"):
    db_file = settings.database_url.replace("sqlite:///", "", 1)
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
