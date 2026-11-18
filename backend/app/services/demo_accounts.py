"""Optional demo administrators bundled as password hashes, never plaintext."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.admin import Admin
from app.services.admin_service import get_admin_by_username

settings = get_settings()
SEED_PATH = Path(__file__).resolve().parents[1] / "seed" / "demo_accounts.json"


def ensure_demo_accounts(db: Session) -> list[str]:
    """Create missing demo accounts only; existing passwords and status win."""
    if not settings.seed_demo_accounts:
        return []
    created = []
    for account in json.loads(SEED_PATH.read_text(encoding="utf-8")):
        if get_admin_by_username(db, account["username"]) is not None:
            continue
        db.add(Admin(
            username=account["username"],
            password_hash=account["password_hash"],
            full_name=account["full_name"],
            is_active=True,
        ))
        created.append(account["username"])
    if created:
        db.commit()
    return created
