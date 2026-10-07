"""Accept legacy URLs and named target lists without changing environment keys."""
import json
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

MULTI_TARGET_FIELDS = {"gpu_url": "GPU", "node_url": "Server", "vllm_url": "vLLM"}


class DashboardTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)

    id: str
    name: str
    url: str

    @field_validator("id", "name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Target fields must not be blank")
        return value

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str, info: ValidationInfo) -> str:
        if not value and (info.context or {}).get("allow_empty_urls"):
            return ""
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Dashboard URL must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Dashboard URL must not contain credentials")
        return value


def parse_dashboard_targets(
    value: str | None, name: str, *, allow_empty_urls: bool = False,
) -> list[DashboardTarget]:
    if not value or not value.strip():
        return []
    value = value.strip()
    try:
        if value.startswith("["):
            entries = json.loads(value)
            targets = [DashboardTarget.model_validate(
                entry, context={"allow_empty_urls": allow_empty_urls},
            ) for entry in entries]
        else:
            targets = [DashboardTarget(id="default", name=name, url=value)]
        if len({target.id for target in targets}) != len(targets):
            raise ValueError("Duplicate target IDs")
        return targets
    except (ValueError, TypeError):
        # Do not include raw configuration/URLs in startup error messages.
        raise ValueError(
            "Expected an HTTP(S) URL or JSON array of {id, name, url}; "
            "IDs/names must be non-empty and IDs unique, without URL credentials; "
            "empty target URLs are supported only for KAC LLM services"
        ) from None
