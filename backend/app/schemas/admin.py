from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.utils.timezone import to_kst_iso_system


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
