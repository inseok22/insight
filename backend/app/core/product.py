"""Delivery profiles. Keep unfinished HPC overview disabled in both profiles."""
from app.core.config import Settings

COMMON = ("gpu", "server")
HPC = ("kubernetes", "network", "job", "power")
LLM = (
    "vllm", "vllm_observability", "trace", "user_trace",
    # LLM 납품에서는 Kubernetes와 Network를 비활성화한다.
    # "kubernetes",
    # "network",
)
DASHBOARD_FEATURES = {
    "overview_url": "hpc_dashboard", "node_url": "server", "job_url": "job",
    "gpu_url": "gpu", "power_url": "power", "k8s_url": "kubernetes",
    "snmp_url": "network", "vllm_url": "vllm",
    "vllm_observability_url": "vllm_observability", "trace_url": "trace",
    "user_trace_url": "user_trace",
}


def product_config(settings: Settings) -> dict:
    is_llm = settings.product_profile == "llm"
    features = list(COMMON + (LLM if is_llm else HPC))
    # EICN 납품: 자원예약 비활성화 (기존 메뉴/라우트/API feature guard 공통 적용).
    # if settings.resource_reservations_enabled:
    #     features.append("resource_reservations")
    if settings.terminal_enabled:
        features.append("terminal")
    if settings.monitoring_scope == "gpu_llm":
        features = ["gpu", "vllm"]
        is_llm = True
    elif settings.monitoring_scope == "kac":
        # 한국공항공사: 나머지 관제/예약/터미널 기능은 직접 접근도 차단한다.
        features = ["vllm", "gpu", "server"]
        is_llm = True
    return {
        "profile": "llm" if is_llm else "hpc",
        "product_name": "T-LLM Observability" if is_llm else "TSlurm Insight",
        "short_name": "T-LLM" if is_llm else "TSlurm",
        "home_path": "/ops/vllm" if is_llm else "/ops/k8s",
        "features": features,
    }
