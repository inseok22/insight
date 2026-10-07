from fastapi import APIRouter

from app.core.config import get_settings
from app.core.dashboard_targets import MULTI_TARGET_FIELDS, parse_dashboard_targets
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
    dashboard_urls = {
        field: getattr(settings, field) if feature in product["features"] else None
        for field, feature in DASHBOARD_FEATURES.items()
    }
    dashboard_targets = {
        field: [target.model_dump() for target in parse_dashboard_targets(
            dashboard_urls[field], name,
            allow_empty_urls=settings.monitoring_scope == "kac" and field == "vllm_url",
        )]
        for field, name in MULTI_TARGET_FIELDS.items()
    }
    # Keep the existing single-URL response usable by older frontends.
    for field, targets in dashboard_targets.items():
        dashboard_urls[field] = (targets[0]["url"] or None) if targets else None
    dashboards = DashboardUrlsResponse(**dashboard_urls)
    terminals = [
        TerminalTargetResponse(
            key=key, name=key.replace("-", " ").title(),
            ws_path=f"/api/v1/ws/term/{key}",
        ) for key in settings.terminal_targets_list
    ] if "terminal" in product["features"] else []
    return FrontendConfigResponse(
        dashboard_layout="services" if settings.monitoring_scope == "kac" else
            "single-server" if settings.monitoring_scope == "gpu_llm" else "eicn",
        **product, dashboards=dashboards, dashboard_targets=dashboard_targets,
        terminals=terminals,
    )
