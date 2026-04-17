from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.user import ApprovalStatus


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    birth_date: str | None = None
    affiliation: str | None = None
    is_active: bool
    approval_status: ApprovalStatus
    created_at: datetime
    updated_at: datetime


class UserAdminRead(UserRead):
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None


class UserApprovalPatch(BaseModel):
    status: ApprovalStatus
    rejection_reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "UserApprovalPatch":
        if self.status == ApprovalStatus.APPROVED:
            self.rejection_reason = None
        return self
