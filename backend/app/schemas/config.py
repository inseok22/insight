from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str


class DashboardUrlsResponse(BaseModel):
    overview_url: str | None = None
    node_url: str | None = None
    job_url: str | None = None
    gpu_url: str | None = None
    power_url: str | None = None
    k8s_url: str | None = None
    snmp_url: str | None = None


class TerminalTargetResponse(BaseModel):
    key: str
    name: str
    ws_path: str


class FrontendConfigResponse(BaseModel):
    dashboards: DashboardUrlsResponse
    terminals: list[TerminalTargetResponse]
