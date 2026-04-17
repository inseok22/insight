from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_user_db
from app.dependencies.auth import AdminUserDep
from app.models.user import ApprovalStatus
from app.schemas.auth import MessageResponse
from app.schemas.user import UserAdminRead, UserApprovalPatch, UserCreate, UserRead
from app.services.user_service import approve_user, create_user, get_user_by_id, list_users, reject_user

router = APIRouter(prefix="/users", tags=["users"])
UserDbDep = Annotated[Session, Depends(get_user_db)]


@router.get("", response_model=list[UserAdminRead])
def read_users(
    _: AdminUserDep,
    db: UserDbDep,
    approval_status: ApprovalStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    is_active: bool | None = Query(default=None),
) -> list[UserAdminRead]:
    return list_users(db, approval_status=approval_status, q=q, is_active=is_active)


@router.get("/{user_id}", response_model=UserAdminRead)
def read_user_detail(user_id: int, _: AdminUserDep, db: UserDbDep) -> UserAdminRead:
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


@router.patch("/{user_id}/approval", response_model=MessageResponse)
def patch_user_approval(user_id: int, payload: UserApprovalPatch, current_admin: AdminUserDep, db: UserDbDep) -> MessageResponse:
    try:
        if payload.status == ApprovalStatus.APPROVED:
            approve_user(db, user_id=user_id, reviewed_by=current_admin.username)
            return MessageResponse(message="신청이 승인 처리되었습니다. (Desk/OpenLDAP 수동 등록 완료)")
        if payload.status == ApprovalStatus.REJECTED:
            reject_user(db, user_id=user_id)
            return MessageResponse(message="신청이 반려되어 삭제되었습니다.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="지원하지 않는 상태입니다.")
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(payload: UserCreate, _: AdminUserDep, db: UserDbDep) -> UserRead:
    try:
        user = create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return user
