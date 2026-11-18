from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.db.session import get_admin_db
from app.dependencies.auth import ActiveAdminDep
from app.models.admin import Admin
from app.schemas.admin import AdminCreate, AdminRead
from app.services.admin_service import AdminUsernameExists, create_admin


class PasswordSafeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                # FastAPI's default validation response can echo raw password input,
                # including malformed JSON. Never return the submitted body here.
                raise HTTPException(422, "입력값을 확인해 주세요. 아이디는 영문·숫자로 시작하는 1~50자(._- 허용), 이름은 100자 이내, 비밀번호는 8~128자입니다.") from None

        return handle


router = APIRouter(prefix="/admin/users", tags=["admin-users"], route_class=PasswordSafeRoute)
AdminDbDep = Annotated[Session, Depends(get_admin_db)]


@router.post("", response_model=AdminRead, status_code=201)
def add_admin(payload: AdminCreate, db: AdminDbDep, current_admin: ActiveAdminDep) -> Admin:
    try:
        return create_admin(db, payload)
    except AdminUsernameExists as exc:
        raise HTTPException(409, str(exc)) from None
