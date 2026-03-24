from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "TSlurmOps API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'tslurm_ops.db').as_posix()}"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

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

    terminal_targets: list[str] = Field(default_factory=lambda: ["master", "node-a", "node-b"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @field_validator("terminal_targets", mode="before")
    @classmethod
    def parse_terminal_targets(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
