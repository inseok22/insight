from pydantic import BaseModel, ConfigDict, Field

from app.schemas.admin import AdminRead
from app.schemas.user import USERNAME_PATTERN, GroupName


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, max_length=50)
    password: str = Field(min_length=4, max_length=128)
    surname: str = Field(min_length=1, max_length=50)        # sn (성)
    given_name: str = Field(min_length=1, max_length=50)     # cn (이름)
    group_name: GroupName = "tslurm"
    email: str | None = Field(default=None, max_length=100)
    birth_date: str | None = Field(default=None, max_length=20)
    affiliation: str | None = Field(default=None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AdminRead


class MessageResponse(BaseModel):
    message: str


class AuthenticatedUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: AdminRead
