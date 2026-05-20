from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_admin_db
from app.dependencies.auth import AdminUserDep
from app.schemas.resource_reservation import (
    ResourceReservationActionResponse,
    ResourceReservationApproveRequest,
    ResourceReservationRejectRequest,
    ResourceReservationRequestListResponse,
    ResourceReservationRetryRequest,
)
from app.services.resource_reservation_service import (
    approve_resource_reservation_request,
    list_resource_reservation_requests,
    reject_resource_reservation_request,
    retry_slurm_reservation_request,
)

router = APIRouter(prefix="/admin/resource", tags=["admin-resource"])
AdminDbDep = Annotated[Session, Depends(get_admin_db)]


@router.get("/reservation-requests", response_model=ResourceReservationRequestListResponse)
def read_resource_reservation_requests(_: AdminUserDep, db: AdminDbDep) -> ResourceReservationRequestListResponse:
    return list_resource_reservation_requests(db)


@router.post("/reservation-requests/{request_id}/approve", response_model=ResourceReservationActionResponse)
def approve_resource_reservation(
    request_id: int,
    payload: ResourceReservationApproveRequest,
    current_admin: AdminUserDep,
    db: AdminDbDep,
) -> ResourceReservationActionResponse:
    try:
        return approve_resource_reservation_request(
            db,
            request_id=request_id,
            admin_username=current_admin.username,
            admin_memo=payload.adminMemo,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/reservation-requests/{request_id}/reject", response_model=ResourceReservationActionResponse)
def reject_resource_reservation(
    request_id: int,
    payload: ResourceReservationRejectRequest,
    current_admin: AdminUserDep,
    db: AdminDbDep,
) -> ResourceReservationActionResponse:
    try:
        return reject_resource_reservation_request(
            db,
            request_id=request_id,
            admin_username=current_admin.username,
            rejection_reason=payload.rejectionReason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/reservation-requests/{request_id}/retry-slurm", response_model=ResourceReservationActionResponse)
def retry_resource_reservation_slurm(
    request_id: int,
    payload: ResourceReservationRetryRequest,
    _: AdminUserDep,
    db: AdminDbDep,
) -> ResourceReservationActionResponse:
    try:
        return retry_slurm_reservation_request(
            db,
            request_id=request_id,
            admin_memo=payload.adminMemo,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
