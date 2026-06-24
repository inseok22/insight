from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UserBase


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(UserBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)    # LDAP uid
    password_hash: Mapped[str] = mapped_column(String(255))                       # {SSHA}, LDAP userPassword
    gecos: Mapped[str] = mapped_column(String(50), default="USER", server_default="USER", nullable=False)  # LDAP gecos (USER 고정)
    surname: Mapped[str | None] = mapped_column(String(50), nullable=True)        # LDAP sn (성)
    given_name: Mapped[str | None] = mapped_column(String(50), nullable=True)     # LDAP cn (이름)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)     # surname+given_name 조합 (표시/검색용)
    group_name: Mapped[str] = mapped_column(String(50), default="tslurm", nullable=False)  # LDAP gidNumber 매핑용
    uid_number: Mapped[int | None] = mapped_column(unique=True, nullable=True)    # LDAP uidNumber, 승인 시 10001~ 발급
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)         # LDAP mail
    birth_date: Mapped[str | None] = mapped_column(String(20), nullable=True)     # 데스크 기록용 (예: "1990-01-15")
    affiliation: Mapped[str | None] = mapped_column(String(100), nullable=True)   # 데스크 기록용 (소속)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        SqlEnum(
            ApprovalStatus,
            name="approval_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            validate_strings=True,
        ),
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
