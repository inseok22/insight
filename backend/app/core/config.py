from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "TSlurmOps API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    admin_database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'insight_admin.db').as_posix()}"
    user_database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'desk_users.db').as_posix()}"

    # str로만 받고 property에서 파싱
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    terminal_targets: str = "master,node-a,node-b"

    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin"
    initial_admin_name: str = "Administrator"

    overview_url: str | None = None
    node_url: str | None = None
    job_url: str | None = None
    gpu_url: str | None = None
    power_url: str | None = None
    k8s_url: str | None = None
    snmp_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def terminal_targets_list(self) -> list[str]:
        return [item.strip() for item in self.terminal_targets.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
