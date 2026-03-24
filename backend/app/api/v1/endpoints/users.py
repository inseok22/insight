from fastapi import APIRouter, HTTPException, status

from app.dependencies.auth import AdminUserDep, DbDep
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import create_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def read_users(_: AdminUserDep, db: DbDep) -> list[UserRead]:
    return list_users(db)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(payload: UserCreate, _: AdminUserDep, db: DbDep) -> UserRead:
    try:
        user = create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return user
