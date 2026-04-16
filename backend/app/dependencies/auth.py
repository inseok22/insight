from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import credentials_exception, decode_access_token, TokenError
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_username

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token")


TokenDep = Annotated[str, Depends(oauth2_scheme)]
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(token: TokenDep, db: DbDep) -> User:
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise credentials_exception from exc

    username = payload.get("sub")
    if not username:
        raise credentials_exception

    user = get_user_by_username(db, username)
    if not user:
        raise credentials_exception
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUserDep) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return current_user


ActiveUserDep = Annotated[User, Depends(get_current_active_user)]


def get_current_admin_user(current_user: ActiveUserDep) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return current_user


AdminUserDep = Annotated[User, Depends(get_current_admin_user)]
