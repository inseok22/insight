from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class MessageResponse(BaseModel):
    message: str


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserRead