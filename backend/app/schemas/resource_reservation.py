from pydantic import BaseModel


class TdResourceReservationResponse(BaseModel):
    accepted: bool
    requestId: str
    status: str
    validationStatus: str
    message: str
    duplicated: bool | None = None


class ReservationAuditLogResponse(BaseModel):
    action: str
    actor: str
    message: str
    createdAt: str


class ResourceReservationRequestResponse(BaseModel):
    id: str
    externalTicketId: str
    status: str
    validationStatus: str
    validationMessages: list[str]
    title: str
    detail: str
    requesterUsername: str
    requesterEmail: str | None
    partitionType: str | None
    slurmPartition: str | None
    requestedCpuCores: int | None
    requestedMemoryGb: int | None
    requestedGpuNodes: int | None
    startAt: str | None
    endAt: str | None
    durationText: str
    durationMinutes: int | None
    slurmReservationName: str | None
    slurmPayloadPreview: object | None
    adminMemo: str | None
    rejectionReason: str | None
    approvedBy: str | None
    approvedAt: str | None
    rejectedBy: str | None
    rejectedAt: str | None
    slurmError: str | None
    createdAt: str
    updatedAt: str
    auditLogs: list[ReservationAuditLogResponse]


class ResourceReservationRequestListResponse(BaseModel):
    generatedAt: str
    items: list[ResourceReservationRequestResponse]


class ResourceReservationApproveRequest(BaseModel):
    adminMemo: str | None = None


class ResourceReservationRejectRequest(BaseModel):
    rejectionReason: str


class ResourceReservationRetryRequest(BaseModel):
    adminMemo: str | None = None


class ResourceReservationActionResponse(BaseModel):
    success: bool
    status: str
    requestId: str
    message: str
    slurmReservationName: str | None = None
    slurmError: str | None = None
