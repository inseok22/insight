from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "TSlurmOps API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    product_profile: Literal["hpc", "llm"] = "llm"
    resource_reservations_enabled: bool = True
    terminal_enabled: bool = True

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
    slurm_reservation_mock: bool = Field(default=True, validation_alias="SLURM_RESERVATION_MOCK")
    slurm_rest_base_url: str = Field(default="http://slurmrestd:6820", validation_alias="SLURM_REST_BASE_URL")
    slurm_rest_api_version: str = Field(default="v0.0.44", validation_alias="SLURM_REST_API_VERSION")
    slurm_rest_user_name: str | None = Field(default=None, validation_alias="SLURM_REST_USER_NAME")
    slurm_rest_user_token: str | None = Field(default=None, validation_alias="SLURM_REST_USER_TOKEN")

    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin"
    initial_admin_name: str = "Administrator"

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
    )

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
