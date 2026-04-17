from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    role: str = "admin"
    is_active: bool
    created_at: datetime
    updated_at: datetime
