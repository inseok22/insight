from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import credentials_exception, decode_access_token, TokenError
from app.db.session import get_admin_db
from app.models.admin import Admin
from app.services.admin_service import get_admin_by_username

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token")


TokenDep = Annotated[str, Depends(oauth2_scheme)]
AdminDbDep = Annotated[Session, Depends(get_admin_db)]


def get_current_admin(token: TokenDep, db: AdminDbDep) -> Admin:
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise credentials_exception from exc

    username = payload.get("sub")
    if not username:
        raise credentials_exception

    admin = get_admin_by_username(db, username)
    if not admin:
        raise credentials_exception
    return admin


CurrentAdminDep = Annotated[Admin, Depends(get_current_admin)]


def get_current_active_admin(current_admin: CurrentAdminDep) -> Admin:
    if not current_admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return current_admin


ActiveAdminDep = Annotated[Admin, Depends(get_current_active_admin)]


def get_current_admin_user(current_admin: ActiveAdminDep) -> Admin:
    return current_admin


AdminUserDep = Annotated[Admin, Depends(get_current_admin_user)]
