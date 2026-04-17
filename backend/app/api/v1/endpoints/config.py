from fastapi import APIRouter

from app.core.config import get_settings
from app.dependencies.auth import ActiveAdminDep
from app.schemas.config import DashboardUrlsResponse, FrontendConfigResponse, TerminalTargetResponse

router = APIRouter(prefix="/config", tags=["config"])
settings = get_settings()


@router.get("/frontend", response_model=FrontendConfigResponse)
def read_frontend_config(_: ActiveAdminDep) -> FrontendConfigResponse:
    dashboards = DashboardUrlsResponse(
        overview_url=settings.overview_url,
        node_url=settings.node_url,
        job_url=settings.job_url,
        gpu_url=settings.gpu_url,
        power_url=settings.power_url,
        k8s_url=settings.k8s_url,
        snmp_url=settings.snmp_url,
    )
    terminals = [
        TerminalTargetResponse(
            key=key,
            name=key.replace("-", " ").title(),
            ws_path=f"/api/v1/ws/term/{key}",
        )
        for key in settings.terminal_targets
    ]
    return FrontendConfigResponse(dashboards=dashboards, terminals=terminals)
