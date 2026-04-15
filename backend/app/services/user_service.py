from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models.user import ApprovalStatus, User, UserRole
from app.schemas.user import UserCreate

settings = get_settings()


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return db.scalar(stmt)


def list_users(
    db: Session,
    *,
    approval_status: ApprovalStatus | None = None,
    q: str | None = None,
    is_active: bool | None = None,
) -> list[User]:
    stmt = select(User).order_by(User.id.asc())
    if approval_status is not None:
        stmt = stmt.where(User.approval_status == approval_status)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if q:
        keyword = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(keyword),
                User.full_name.ilike(keyword),
                User.email.ilike(keyword),
            )
        )
    return list(db.scalars(stmt).all())


def get_user_by_id(db: Session, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return db.scalar(stmt)


def create_user(db: Session, payload: UserCreate) -> User:
    existing = get_user_by_username(db, payload.username)
    if existing:
        raise ValueError("이미 존재하는 사용자 아이디입니다.")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        email=payload.email,
        birth_date=payload.birth_date,
        affiliation=payload.affiliation,
        role=payload.role,
        is_active=payload.is_active,
        approval_status=payload.approval_status,
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


def approve_user(db: Session, *, user_id: int, reviewed_by: str) -> User:
    user = get_user_by_id(db, user_id)
    if not user:
        raise LookupError("사용자를 찾을 수 없습니다.")
    if user.approval_status != ApprovalStatus.PENDING:
        raise ValueError("이미 처리된 신청입니다.")

    user.approval_status = ApprovalStatus.APPROVED
    user.is_active = False
    user.reviewed_at = datetime.now(timezone.utc)
    user.reviewed_by = reviewed_by
    user.rejection_reason = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def reject_user(db: Session, *, user_id: int) -> None:
    user = get_user_by_id(db, user_id)
    if not user:
        raise LookupError("사용자를 찾을 수 없습니다.")
    if user.approval_status != ApprovalStatus.PENDING:
        raise ValueError("이미 처리된 신청입니다.")
    db.delete(user)
    db.commit()
