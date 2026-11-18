from functools import lru_cache
import base64
import binascii
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.admin_passwords import ADMIN_PASSWORD_ITERATIONS, parse_admin_password_hash
from app.core.dashboard_targets import parse_dashboard_targets

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "TSlurmOps API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    backend_port: int = Field(default=18000, ge=1, le=65535)
    product_profile: Literal["hpc", "llm"] = "llm"
    monitoring_scope: Literal["profile", "gpu_llm", "kac"] = "profile"
    resource_reservations_enabled: bool = True
    terminal_enabled: bool = True

    # Shared demo chat; deployment-specific connections stay in backend environment settings.
    demo_chat_enabled: bool = False
    vllm_api_base_url: str = ""
    vllm_model: str = ""
    vllm_api_key: str = Field(default="", repr=False)
    vllm_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    langfuse_base_url: str = ""
    langfuse_public_key: str = Field(default="", repr=False)
    langfuse_secret_key: str = Field(default="", repr=False)
    langfuse_tracing_enabled: bool = False

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    admin_database_url: str = Field(
        default="mysql+pymysql://insight_admin_user:change-me@127.0.0.1:3306/insight_admin?charset=utf8mb4",
        validation_alias="ADMIN_DATABASE_URL",
    )
    user_database_url: str = Field(
        default="mysql+pymysql://desk_user_user:change-me@127.0.0.1:3306/desk_users?charset=utf8mb4",
        validation_alias="USER_DATABASE_URL",
    )

    # str로만 받고 property에서 파싱
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    terminal_targets: str = "master,node-a,node-b"
    td_api_key: str | None = Field(default=None, validation_alias="TD_API_KEY")
    slurm_rest_base_url: str = Field(default="http://slurmrestd:6820", validation_alias="SLURM_REST_BASE_URL")
    slurm_rest_api_version: str = Field(default="v0.0.44", validation_alias="SLURM_REST_API_VERSION")
    slurm_rest_user_name: str | None = Field(default=None, validation_alias="SLURM_REST_USER_NAME")
    slurm_rest_user_token: str | None = Field(default=None, validation_alias="SLURM_REST_USER_TOKEN")

    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin"
    initial_admin_password_hash: str | None = None
    initial_admin_name: str = "Administrator"
    # Legacy setting accepted for older env files; startup no longer seeds demo users.
    seed_demo_accounts: bool = False

    # LSC(OpenLDAP 동기화) 원격 실행 설정 — 승인 시 SSH로 스크립트 실행
    lsc_sync_enabled: bool = Field(default=True, validation_alias="LSC_SYNC_ENABLED")
    lsc_ssh_host: str = Field(default="192.168.0.125", validation_alias="LSC_SSH_HOST")
    lsc_ssh_port: int = Field(default=10022, validation_alias="LSC_SSH_PORT")
    lsc_ssh_user: str = Field(default="root", validation_alias="LSC_SSH_USER")
    lsc_ssh_key_path: str | None = Field(default=None, validation_alias="LSC_SSH_KEY_PATH")
    lsc_ssh_timeout: int = Field(default=120, validation_alias="LSC_SSH_TIMEOUT")
    lsc_sync_command: str = Field(
        default="/usr/local/bin/lsc-sync-now.sh && /usr/local/bin/make_home.sh",
        validation_alias="LSC_SYNC_COMMAND",
    )

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

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("gpu_url", "node_url", "vllm_url")
    @classmethod
    def validate_dashboard_targets(cls, value: str | None, info: ValidationInfo) -> str | None:
        is_kac = info.data.get("monitoring_scope") == "kac"
        if is_kac and value and value.strip().startswith("["):
            raise ValueError("KAC GPU_URL/NODE_URL/VLLM_URL must each be one HTTP(S) URL or empty; replace the old service list")
        parse_dashboard_targets(value, "Dashboard")
        return value

    @field_validator("vllm_api_base_url", "langfuse_base_url")
    @classmethod
    def validate_chat_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value:
            parsed = urlsplit(value)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.query or parsed.fragment):
                raise ValueError("Use an HTTP(S) base URL without credentials, query or fragment")
        return value

    @field_validator("initial_admin_password_hash")
    @classmethod
    def validate_initial_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = parse_admin_password_hash(value)
        if parsed is not None and parsed[0] >= ADMIN_PASSWORD_ITERATIONS:
            return value
        try:
            if value.startswith("{SSHA}") and len(base64.b64decode(value[6:], validate=True)) >= 28:
                return value
        except (ValueError, binascii.Error):
            pass
        raise ValueError("Expected a PBKDF2-HMAC-SHA256 hash (600000+ iterations) or a legacy salted SSHA hash")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: bool | str) -> bool | str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"debug", "development", "dev"}:
                return True
            if normalized in {"release", "production", "prod"}:
                return False
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def terminal_targets_list(self) -> list[str]:
        return [item.strip() for item in self.terminal_targets.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
