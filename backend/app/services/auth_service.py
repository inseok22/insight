from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.admin import Admin
from app.schemas.auth import TokenResponse
from app.schemas.admin import AdminRead

settings = get_settings()


def build_token_response(admin: Admin) -> TokenResponse:
    token = create_access_token(
        subject=admin.username,
        extra_claims={
            "role": admin.role,
            "full_name": admin.full_name,
        },
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=AdminRead.model_validate(admin),
    )
