from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings


@dataclass(frozen=True)
class SlurmReservationResult:
    success: bool
    response_json: object | None = None
    error: str | None = None


def create_or_update_slurm_reservation(payload: dict[str, object]) -> SlurmReservationResult:
    settings = get_settings()
    if settings.slurm_reservation_mock:
        return SlurmReservationResult(
            success=True,
            response_json={
                "mock": True,
                "result": "success",
                "message": "Mock Slurm reservation created",
            },
        )

    if not settings.slurm_rest_user_name or not settings.slurm_rest_user_token:
        return SlurmReservationResult(success=False, error="Slurm REST user name/token is not configured.")

    base_url = settings.slurm_rest_base_url.rstrip("/")
    api_version = settings.slurm_rest_api_version.strip("/")
    url = f"{base_url}/slurm/{api_version}/reservation"
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-SLURM-USER-NAME": settings.slurm_rest_user_name,
            "X-SLURM-USER-TOKEN": settings.slurm_rest_user_token,
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            return SlurmReservationResult(success=True, response_json=_decode_json_or_text(response_body))
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return SlurmReservationResult(
            success=False,
            response_json=_decode_json_or_text(response_body),
            error=f"Slurm API returned HTTP {exc.code}: {response_body}",
        )
    except URLError as exc:
        return SlurmReservationResult(success=False, error=f"Slurm API request failed: {exc.reason}")
    except OSError as exc:
        return SlurmReservationResult(success=False, error=f"Slurm API request failed: {exc}")


def _decode_json_or_text(value: str) -> object:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
