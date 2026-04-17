from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_admin_db, get_user_db
from app.dependencies.auth import ActiveAdminDep
from app.schemas.auth import AuthenticatedUserResponse, LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import build_token_response
from app.services.admin_service import authenticate_admin
from app.services.user_service import create_user

router = APIRouter(prefix="/auth", tags=["auth"])
AdminDbDep = Annotated[Session, Depends(get_admin_db)]
UserDbDep = Annotated[Session, Depends(get_user_db)]


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: AdminDbDep) -> TokenResponse:
    admin = authenticate_admin(db, payload.username, payload.password)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return build_token_response(admin)


@router.post("/token", response_model=TokenResponse)
def issue_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: AdminDbDep) -> TokenResponse:
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.", headers={"WWW-Authenticate": "Bearer"})
    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="비활성 사용자입니다.")
    return build_token_response(admin)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: UserDbDep) -> UserRead:
    user_data = UserCreate(
        username=payload.username,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
        birth_date=payload.birth_date,
        affiliation=payload.affiliation,
    )
    try:
        user = create_user(db, user_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return user


@router.get("/me", response_model=AuthenticatedUserResponse)
def read_me(current_admin: ActiveAdminDep) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(user=current_admin)
