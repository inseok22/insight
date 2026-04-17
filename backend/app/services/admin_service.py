from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.admin import Admin

settings = get_settings()


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    stmt = select(Admin).where(Admin.username == username)
    return db.scalar(stmt)


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = get_admin_by_username(db, username)
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    return admin


def ensure_initial_admin(db: Session) -> None:
    existing = get_admin_by_username(db, settings.initial_admin_username)
    if existing:
        return

    admin = Admin(
        username=settings.initial_admin_username,
        password_hash=hash_password(settings.initial_admin_password),
        full_name=settings.initial_admin_name,
        is_active=True,
    )
    db.add(admin)
    db.commit()
