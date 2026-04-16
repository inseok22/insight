from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.config import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", app_name=settings.app_name)
