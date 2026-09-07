from fastapi import APIRouter

from app.core.config import get_settings
from app.core.product import DASHBOARD_FEATURES, product_config
from app.dependencies.auth import ActiveAdminDep
from app.schemas.config import (
    DashboardUrlsResponse, FrontendConfigResponse, ProductConfigResponse, TerminalTargetResponse,
)

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/product", response_model=ProductConfigResponse)
def read_product_config() -> ProductConfigResponse:
    # Public branding and feature names only; never expose connection settings here.
    return ProductConfigResponse(**product_config(get_settings()))


@router.get("/frontend", response_model=FrontendConfigResponse)
def read_frontend_config(_: ActiveAdminDep) -> FrontendConfigResponse:
    settings = get_settings()
    product = product_config(settings)
    dashboards = DashboardUrlsResponse(**{
        field: getattr(settings, field) if feature in product["features"] else None
        for field, feature in DASHBOARD_FEATURES.items()
    })
    terminals = [
        TerminalTargetResponse(
            key=key, name=key.replace("-", " ").title(),
            ws_path=f"/api/v1/ws/term/{key}",
        ) for key in settings.terminal_targets_list
    ] if "terminal" in product["features"] else []
    return FrontendConfigResponse(**product, dashboards=dashboards, terminals=terminals)
