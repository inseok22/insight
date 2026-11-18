from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer, field_validator

from app.utils.timezone import to_kst_iso_system


class AdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    username: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    full_name: str | None = Field(default=None, max_length=100)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("username", "full_name", mode="before")
    @classmethod
    def trim_identity(cls, value):
        return value.strip() if isinstance(value, str) else value


class AdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    role: str = "admin"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_system_datetime(self, value: datetime) -> str | None:
        return to_kst_iso_system(value)
