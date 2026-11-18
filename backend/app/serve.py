"""Start the API on BACKEND_PORT (environment or the local backend .env)."""
import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    # Demo conversations are process-local; ignore WEB_CONCURRENCY overrides.
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.backend_port, workers=1)


if __name__ == "__main__":
    main()
