from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=16000)
    request_id: UUID

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("메시지를 입력해 주세요.")
        return value


class ChatStop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
