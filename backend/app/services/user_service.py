from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import ApprovalStatus, User
from app.schemas.user import UserCreate


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
        surname=payload.surname,
        given_name=payload.given_name,
        full_name=f"{payload.surname}{payload.given_name}",  # 성+이름 (표시/검색용)
        group_name=payload.group_name,
        email=payload.email,
        birth_date=payload.birth_date,
        affiliation=payload.affiliation,
        is_active=False,
        approval_status=ApprovalStatus.PENDING,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
