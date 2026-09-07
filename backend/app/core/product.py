"""Delivery profiles. Keep unfinished HPC overview disabled in both profiles."""
from app.core.config import Settings

COMMON = ("kubernetes", "gpu", "server", "network")
LLM = ("vllm", "vllm_observability", "trace", "user_trace")
DASHBOARD_FEATURES = {
    "overview_url": "hpc_dashboard", "node_url": "server", "job_url": "job",
    "gpu_url": "gpu", "power_url": "power", "k8s_url": "kubernetes",
    "snmp_url": "network", "vllm_url": "vllm",
    "vllm_observability_url": "vllm_observability", "trace_url": "trace",
    "user_trace_url": "user_trace",
}


def product_config(settings: Settings) -> dict:
    is_llm = settings.product_profile == "llm"
    features = list(COMMON + (LLM if is_llm else ("job", "power")))
    if settings.resource_reservations_enabled:
        features.append("resource_reservations")
    if settings.terminal_enabled:
        features.append("terminal")
    return {
        "profile": settings.product_profile,
        "product_name": "T-LLM Observability" if is_llm else "TSlurm Insight",
        "short_name": "T-LLM" if is_llm else "TSlurm",
        "home_path": "/ops/vllm" if is_llm else "/ops/k8s",
        "features": features,
    }
