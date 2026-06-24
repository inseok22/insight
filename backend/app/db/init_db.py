from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.base import AdminBase, UserBase
from app.db.session import AdminSessionLocal, admin_engine, user_engine
from app.models import admin, resource_reservation, user  # noqa: F401  # 모델 import로 metadata 등록
from app.services.admin_service import ensure_initial_admin


def init_db() -> None:
    # admin/user metadata는 각각 분리된 database(schema)에 생성된다.
    AdminBase.metadata.create_all(bind=admin_engine)
    UserBase.metadata.create_all(bind=user_engine)
    ensure_resource_reservation_schema()
    ensure_user_gecos_column()
    with AdminSessionLocal() as db:  # type: Session
        ensure_initial_admin(db)


def ensure_user_gecos_column() -> None:
    inspector = inspect(user_engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "gecos" in columns:
        return

    with user_engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN gecos VARCHAR(50) NOT NULL DEFAULT 'USER'"))


def ensure_resource_reservation_schema() -> None:
    inspector = inspect(admin_engine)
    if "resource_reservation_requests" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("resource_reservation_requests")}
    if "admin_memo" in columns:
        return

    with admin_engine.begin() as connection:
        connection.execute(text("ALTER TABLE resource_reservation_requests ADD COLUMN admin_memo TEXT"))
