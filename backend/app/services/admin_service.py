from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import admin_password_needs_update, hash_admin_password, verify_password
from app.models.admin import Admin
from app.schemas.admin import AdminCreate

settings = get_settings()


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    stmt = select(Admin).where(Admin.username == username)
    return db.scalar(stmt)


class AdminUsernameExists(ValueError):
    pass


def create_admin(db: Session, payload: AdminCreate) -> Admin:
    if get_admin_by_username(db, payload.username) is not None:
        raise AdminUsernameExists("이미 사용 중인 아이디입니다.")
    admin = Admin(
        username=payload.username,
        full_name=payload.full_name or None,
        password_hash=hash_admin_password(payload.password.get_secret_value()),
        is_active=True,
    )
    db.add(admin)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # The unique constraint also protects simultaneous requests for the same ID.
        if get_admin_by_username(db, payload.username) is not None:
            raise AdminUsernameExists("이미 사용 중인 아이디입니다.") from None
        raise
    db.refresh(admin)
    return admin


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = get_admin_by_username(db, username)
    if not admin:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    if admin.is_active and admin_password_needs_update(admin.password_hash):
        # Do not overwrite a password reset or another login's migration.
        admin_id = admin.id
        result = db.execute(update(Admin).where(
            Admin.id == admin_id,
            Admin.password_hash == admin.password_hash,
            Admin.is_active.is_(True),
        ).values(password_hash=hash_admin_password(password)).execution_options(synchronize_session=False))
        if result.rowcount == 1:
            db.commit()
        else:
            db.rollback()
        # Re-check the latest row even when the migration won the race: a reset,
        # account removal or deactivation may have happened immediately after it.
        admin = db.get(Admin, admin_id, populate_existing=True)
        if admin is None or not verify_password(password, admin.password_hash):
            return None
    return admin


def ensure_initial_admin(db: Session) -> None:
    existing = get_admin_by_username(db, settings.initial_admin_username)
    if existing:
        return

    admin = Admin(
        username=settings.initial_admin_username,
        password_hash=settings.initial_admin_password_hash or hash_admin_password(settings.initial_admin_password),
        full_name=settings.initial_admin_name,
        is_active=True,
    )
    db.add(admin)
    db.commit()
