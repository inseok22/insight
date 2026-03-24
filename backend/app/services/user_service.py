from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

settings = get_settings()


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.scalar(stmt)


def list_users(db: Session) -> list[User]:
    stmt = select(User).order_by(User.id.asc())
    return list(db.scalars(stmt).all())


def create_user(db: Session, payload: UserCreate) -> User:
    existing = get_user_by_username(db, payload.username)
    if existing:
        raise ValueError("이미 존재하는 사용자 아이디입니다.")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def ensure_initial_admin(db: Session) -> None:
    existing = get_user_by_username(db, settings.initial_admin_username)
    if existing:
        return

    admin = User(
        username=settings.initial_admin_username,
        password_hash=hash_password(settings.initial_admin_password),
        full_name=settings.initial_admin_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
