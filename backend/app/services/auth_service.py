from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead

settings = get_settings()


def build_token_response(user: User) -> TokenResponse:
    token = create_access_token(
        subject=user.username,
        extra_claims={
            "role": user.role.value,
            "full_name": user.full_name,
        },
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserRead.model_validate(user),
    )
