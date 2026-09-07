from typing import Literal
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
    vllm_url: str | None = None
    vllm_observability_url: str | None = None
    trace_url: str | None = None
    user_trace_url: str | None = None


class TerminalTargetResponse(BaseModel):
    key: str
    name: str
    ws_path: str


class ProductConfigResponse(BaseModel):
    profile: Literal["hpc", "llm"]
    product_name: str
    short_name: str
    home_path: str
    features: list[str]


class FrontendConfigResponse(ProductConfigResponse):
    dashboards: DashboardUrlsResponse
    terminals: list[TerminalTargetResponse]
