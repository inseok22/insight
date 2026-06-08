from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.models.user import ApprovalStatus
from app.utils.timezone import to_kst_iso_system

# LDAP uid / POSIX 계정명 규칙: 소문자로 시작, 소문자·숫자·-·_ 만, 3~32자
USERNAME_PATTERN = r"^[a-z][a-z0-9_-]{2,31}$"

# 그룹 라벨 → LDAP gidNumber 매핑 (현재는 tslurm만)
GROUP_GID_MAP: dict[str, int] = {"tslurm": 10002}
GroupName = Literal["tslurm"]


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, max_length=50)
    password: str = Field(min_length=4, max_length=128)
    surname: str = Field(min_length=1, max_length=50)        # sn (성)
    given_name: str = Field(min_length=1, max_length=50)     # cn (이름)
    group_name: GroupName = "tslurm"                         # gidNumber 매핑
    email: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    surname: str | None = None
    given_name: str | None = None
    full_name: str | None = None
    group_name: str | None = None
    uid_number: int | None = None
    email: str | None = None
    birth_date: str | None = None
    affiliation: str | None = None
    is_active: bool
    approval_status: ApprovalStatus
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_system_datetime(self, value: datetime) -> str | None:
        return to_kst_iso_system(value)


class UserAdminRead(UserRead):
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None

    @field_serializer("reviewed_at")
    def serialize_reviewed_at(self, value: datetime | None) -> str | None:
        return to_kst_iso_system(value)


class UserApprovalPatch(BaseModel):
    status: ApprovalStatus
    rejection_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "UserApprovalPatch":
        if self.status == ApprovalStatus.APPROVED:
            self.rejection_reason = None
        return self
