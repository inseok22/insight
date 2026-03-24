from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import ActiveUserDep
from app.schemas.auth import AuthenticatedUserResponse, LoginRequest, TokenResponse
from app.services.auth_service import build_token_response
from app.services.user_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])
DbDep = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbDep) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return build_token_response(user)


@router.post("/token", response_model=TokenResponse)
def issue_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep) -> TokenResponse:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return build_token_response(user)


@router.get("/me", response_model=AuthenticatedUserResponse)
def read_me(current_user: ActiveUserDep) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(user=current_user)
