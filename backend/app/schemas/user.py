from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=100)
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    birth_date: str | None = None
    affiliation: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime