from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)        # 추가
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)    # 추가 (예: "1990-01-15")
    affiliation: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 추가 (소속)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SqlEnum(ApprovalStatus),
        default=ApprovalStatus.PENDING,
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
