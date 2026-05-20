from json import JSONDecodeError
from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_admin_db
from app.schemas.resource_reservation import TdResourceReservationResponse
from app.services.resource_reservation_service import (
    VALIDATION_ERROR,
    receive_resource_reservation_request,
)

router = APIRouter(prefix="/external/td", tags=["external-td"])


def verify_td_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_td_api_key: Annotated[str | None, Header(alias="X-TD-API-KEY")] = None,
) -> None:
    settings = get_settings()
    token = x_td_api_key
    if not token and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-TD-API-KEY 또는 Authorization: Bearer 토큰이 필요합니다.",
        )
    if not settings.td_api_key or not compare_digest(token, settings.td_api_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API 키가 올바르지 않습니다.")


@router.post(
    "/resource-reservation-requests",
    response_model=TdResourceReservationResponse,
    response_model_exclude_none=True,
)
async def create_td_resource_reservation_request(
    request: Request,
    _: Annotated[None, Depends(verify_td_api_key)],
    db: Annotated[Session, Depends(get_admin_db)],
    x_source: Annotated[str | None, Header(alias="X-Source")] = None,
) -> TdResourceReservationResponse:
    try:
        payload = await request.json()
    except (JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON request body.") from exc

    result = receive_resource_reservation_request(db, payload, source_hint=x_source)
    reservation_request = result.request
    if result.duplicated:
        return TdResourceReservationResponse(
            accepted=True,
            requestId=str(reservation_request.id),
            status=reservation_request.status,
            validationStatus=reservation_request.validation_status,
            duplicated=True,
            message="이미 접수된 예약 요청입니다.",
        )

    if reservation_request.validation_status == VALIDATION_ERROR:
        message = "자원 예약 요청은 접수되었지만 검증 오류가 있습니다."
    else:
        message = "자원 예약 요청이 접수되었습니다."

    return TdResourceReservationResponse(
        accepted=True,
        requestId=str(reservation_request.id),
        status=reservation_request.status,
        validationStatus=reservation_request.validation_status,
        message=message,
    )
