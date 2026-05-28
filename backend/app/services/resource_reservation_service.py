from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.resource_reservation import ResourceReservationRequest
from app.schemas.resource_reservation import (
    ReservationAuditLogResponse,
    ResourceReservationActionResponse,
    ResourceReservationRequestListResponse,
    ResourceReservationRequestResponse,
    SlurmReservationItem,
    SlurmReservationListResponse,
)
from app.services.slurm_service import create_or_update_slurm_reservation, list_slurm_reservations
from app.utils.timezone import (
    KST,
    epoch_seconds_from_kst_business_datetime,
    now_kst,
    parse_td_schedule_as_kst,
    to_kst_iso_business,
    to_kst_iso_system,
)

STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_APPLYING_TO_SLURM = "APPLYING_TO_SLURM"
STATUS_SLURM_RESERVED = "SLURM_RESERVED"
STATUS_SLURM_APPLY_FAILED = "SLURM_APPLY_FAILED"
STATUS_REJECTED = "REJECTED"
VALIDATION_OK = "OK"
VALIDATION_ERROR = "ERROR"


@dataclass(frozen=True)
class ReservationCreateResult:
    request: ResourceReservationRequest
    duplicated: bool


def receive_resource_reservation_request(
    db: Session,
    payload: object,
    source_hint: str | None = None,
) -> ReservationCreateResult:
    payload = _with_source_hint(payload, source_hint)
    existing = _find_existing_request(db, payload)
    if existing:
        return ReservationCreateResult(request=existing, duplicated=True)

    request = _build_request(payload)
    db.add(request)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _find_existing_request(db, payload)
        if existing:
            return ReservationCreateResult(request=existing, duplicated=True)
        raise
    db.refresh(request)
    return ReservationCreateResult(request=request, duplicated=False)


def _with_source_hint(payload: object, source_hint: str | None) -> object:
    """본문에 sourceSystem이 없으면 X-Source 헤더 값으로 채운다."""
    if isinstance(payload, dict) and source_hint and not payload.get("sourceSystem"):
        merged = dict(payload)
        merged["sourceSystem"] = source_hint
        return merged
    return payload


def list_resource_reservation_requests(db: Session) -> ResourceReservationRequestListResponse:
    statement = select(ResourceReservationRequest).order_by(ResourceReservationRequest.created_at.desc(), ResourceReservationRequest.id.desc())
    requests = db.execute(statement).scalars().all()
    return ResourceReservationRequestListResponse(
        generatedAt=now_kst().isoformat(timespec="seconds"),
        items=[_to_list_item(request) for request in requests],
    )


def list_resource_reservations(db: Session) -> SlurmReservationListResponse:
    """실제 Slurm(GET /reservations)에 등록된 예약을 조회하고 Insight DB와 교차해 반환한다.

    MOCK 모드면 Slurm을 호출하지 않고 빈 목록을 반환한다(slurm_service에서 처리).
    조회 실패 시 RuntimeError를 던져 호출부(엔드포인트)가 502로 변환한다.
    """
    result = list_slurm_reservations()
    now = now_kst()
    generated_at = now.isoformat(timespec="seconds")
    if not result.success:
        raise RuntimeError(result.error or "Slurm 예약 정보를 조회하지 못했습니다.")

    by_name = _index_reserved_requests(db)
    items: list[SlurmReservationItem] = []
    for index, raw in enumerate(result.reservations):
        item = _build_slurm_reservation_item(raw, by_name, now, index)
        if item is not None:
            items.append(item)
    return SlurmReservationListResponse(generatedAt=generated_at, items=items)


def _index_reserved_requests(db: Session) -> dict[str, ResourceReservationRequest]:
    statement = select(ResourceReservationRequest).where(ResourceReservationRequest.slurm_reservation_name.isnot(None))
    by_name: dict[str, ResourceReservationRequest] = {}
    for request in db.execute(statement).scalars().all():
        if request.slurm_reservation_name:
            by_name.setdefault(request.slurm_reservation_name, request)
    return by_name


def _build_slurm_reservation_item(
    raw: object,
    by_name: dict[str, ResourceReservationRequest],
    now: datetime,
    index: int,
) -> SlurmReservationItem | None:
    if not isinstance(raw, dict):
        return None

    name = _raw_text(raw.get("name")) or ""
    db_req = by_name.get(name) if name else None

    start_dt = _slurm_epoch_to_kst(raw.get("start_time"))
    end_dt = _slurm_epoch_to_kst(raw.get("end_time"))
    slurm_partition = _raw_text(raw.get("partition")) or ""
    tres = _blank_to_none(_raw_text(raw.get("tres")))
    node_count = _slurm_number(raw.get("node_count"))
    users = _slurm_users(raw.get("users"))

    if db_req and db_req.partition_type:
        partition_type = db_req.partition_type
    else:
        partition_type = _infer_partition_type(slurm_partition, tres)

    if db_req:
        cpu_cores = db_req.requested_cpu_cores
        memory_gb = db_req.requested_memory_gb
        gpu_node_count = db_req.requested_gpu_nodes
    else:
        cpu_cores, memory_gb = _parse_tres_cpu_mem(tres)
        gpu_node_count = node_count if partition_type == "GPU" else None

    requester = db_req.requester_username if (db_req and db_req.requester_username) else (users[0] if users else "")
    title = db_req.title if (db_req and db_req.title) else name

    return SlurmReservationItem(
        id=name or f"resv-{index}",
        reservationName=name,
        displayStatus=_derive_reservation_status(start_dt, end_dt, now, name),
        source="INSIGHT" if db_req else "SLURM_MANUAL",
        externalTicketId=(db_req.external_ticket_id if db_req else None),
        title=title,
        requesterUsername=requester,
        requesterEmail=(db_req.notification_email if db_req else None),
        users=users,
        partitionType=partition_type,
        slurmPartition=slurm_partition,
        startAt=start_dt.isoformat(timespec="seconds") if start_dt else "",
        endAt=end_dt.isoformat(timespec="seconds") if end_dt else "",
        durationText=_format_duration_minutes(_minutes_between(start_dt, end_dt)),
        cpuCores=cpu_cores,
        memoryGb=memory_gb,
        gpuNodeCount=gpu_node_count,
        nodeList=_blank_to_none(_raw_text(raw.get("node_list"))),
        tres=tres,
        comment=_blank_to_none(_raw_text(raw.get("comment"))),
        slurmExists=True,
        insightRequestExists=db_req is not None,
        lastSyncedAt=now.isoformat(timespec="seconds"),
    )


def _slurm_number(value: object) -> int | None:
    """Slurm 응답의 숫자 필드를 int로 정규화한다(평문 int 또는 {set,infinite,number} 래퍼 모두 지원)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        if value.get("set") is False or value.get("infinite") is True:
            return None
        number = value.get("number")
        if isinstance(number, (int, float)) and not isinstance(number, bool):
            return int(number)
    return None


def _slurm_epoch_to_kst(value: object) -> datetime | None:
    ts = _slurm_number(value)
    if ts is None or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(KST)
    except (OverflowError, OSError, ValueError):
        return None


def _slurm_users(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = _raw_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _infer_partition_type(partition: str | None, tres: str | None) -> str:
    haystack = f"{partition or ''} {tres or ''}".lower()
    if "gpu" in haystack:
        return "GPU"
    if "bigmem" in haystack:
        return "BIGMEM"
    return "GENERAL"


def _parse_tres_cpu_mem(tres: str | None) -> tuple[int | None, int | None]:
    cpu: int | None = None
    mem: int | None = None
    if not tres:
        return cpu, mem
    for part in tres.split(","):
        item = part.strip()
        if item.startswith("cpu="):
            try:
                cpu = int(item[4:])
            except ValueError:
                pass
        elif item.startswith("mem="):
            mem = _parse_mem_to_gb(item[4:].strip())
    return cpu, mem


def _parse_mem_to_gb(raw: str) -> int | None:
    if not raw:
        return None
    text = raw.upper()
    try:
        if text.endswith("T"):
            return int(float(text[:-1]) * 1024)
        if text.endswith("G"):
            return int(float(text[:-1]))
        if text.endswith("M"):
            return int(float(text[:-1]) / 1024)
        return int(float(text))
    except ValueError:
        return None


def _minutes_between(start_dt: datetime | None, end_dt: datetime | None) -> int | None:
    if start_dt is None or end_dt is None:
        return None
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return minutes if minutes > 0 else None


def _format_duration_minutes(total: int | None) -> str:
    if total is None or total <= 0:
        return ""
    days, remainder = divmod(total, 1440)
    hours, minutes = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return "".join(parts) or "0m"


def _derive_reservation_status(
    start_dt: datetime | None,
    end_dt: datetime | None,
    now: datetime,
    name: str,
) -> str:
    if not name or start_dt is None or end_dt is None:
        return "ERROR"
    if now < start_dt:
        return "UPCOMING"
    if start_dt <= now < end_dt:
        return "RUNNING"
    return "ENDED"


def approve_resource_reservation_request(
    db: Session,
    *,
    request_id: int,
    admin_username: str,
    admin_memo: str | None = None,
) -> ResourceReservationActionResponse:
    request = _get_request_or_raise(db, request_id)
    if request.status != STATUS_PENDING_APPROVAL:
        raise ValueError("승인 대기 상태의 요청만 승인할 수 있습니다.")
    if request.validation_status == VALIDATION_ERROR:
        raise ValueError("검증 오류가 있는 요청은 승인할 수 없습니다.")

    payload = build_slurm_reservation_payload(request)
    now = datetime.now(timezone.utc)
    request.slurm_reservation_name = str(payload["name"])
    request.slurm_payload_json = payload
    request.admin_memo = _blank_to_none(admin_memo)
    request.approved_by = admin_username
    request.approved_at = now
    request.status = STATUS_APPLYING_TO_SLURM
    request.slurm_error = None
    request.updated_at = now
    db.commit()
    db.refresh(request)
    return _apply_slurm_payload(db, request, success_message="Slurm 예약 생성이 완료되었습니다.")


def reject_resource_reservation_request(
    db: Session,
    *,
    request_id: int,
    admin_username: str,
    rejection_reason: str,
) -> ResourceReservationActionResponse:
    request = _get_request_or_raise(db, request_id)
    if request.status not in {STATUS_PENDING_APPROVAL, STATUS_VALIDATION_FAILED, STATUS_SLURM_APPLY_FAILED}:
        raise ValueError("현재 상태에서는 예약 요청을 거절할 수 없습니다.")

    reason = _blank_to_none(rejection_reason)
    if not reason:
        raise ValueError("거절 사유를 입력해 주세요.")

    now = datetime.now(timezone.utc)
    request.status = STATUS_REJECTED
    request.rejected_by = admin_username
    request.rejected_at = now
    request.rejection_reason = reason
    request.updated_at = now
    db.commit()
    db.refresh(request)
    return ResourceReservationActionResponse(
        success=True,
        status=request.status,
        requestId=str(request.id),
        message="예약 요청이 거절되었습니다.",
    )


def retry_slurm_reservation_request(
    db: Session,
    *,
    request_id: int,
    admin_memo: str | None = None,
) -> ResourceReservationActionResponse:
    request = _get_request_or_raise(db, request_id)
    if request.status != STATUS_SLURM_APPLY_FAILED:
        raise ValueError("Slurm 반영 실패 상태의 요청만 재시도할 수 있습니다.")

    payload = request.slurm_payload_json if isinstance(request.slurm_payload_json, dict) else build_slurm_reservation_payload(request)
    if "name" not in payload:
        payload = build_slurm_reservation_payload(request)
    now = datetime.now(timezone.utc)
    request.slurm_reservation_name = str(payload["name"])
    request.slurm_payload_json = payload
    if admin_memo is not None:
        request.admin_memo = _blank_to_none(admin_memo)
    request.status = STATUS_APPLYING_TO_SLURM
    request.slurm_error = None
    request.updated_at = now
    db.commit()
    db.refresh(request)
    return _apply_slurm_payload(db, request, success_message="Slurm 예약 생성이 완료되었습니다.")


def build_slurm_reservation_payload(request: ResourceReservationRequest) -> dict[str, object]:
    errors = _validate_for_slurm_payload(request)
    if errors:
        raise ValueError("Slurm payload를 생성할 수 없습니다: " + " ".join(errors))

    # reservation name은 externalTicketId를 우선 사용한다(slurmrestd 목표 포맷). 재시도 시에는
    # 처음 정한 이름(slurm_reservation_name)을 그대로 재사용한다.
    reservation_name = _safe_slurm_reservation_name(
        request.slurm_reservation_name or request.external_ticket_id or f"insight-rsv-{request.id}"
    )
    payload: dict[str, object] = {
        "name": reservation_name,
        "users": request.requester_username,
        "partition": request.slurm_partition,
        "start_time": {"set": True, "infinite": False, "number": epoch_seconds_from_kst_business_datetime(request.start_at)},
        "duration": {"set": True, "infinite": False, "number": request.duration_minutes},
        "flags": ["IGNORE_JOBS"],
        "comment": (
            f"source={request.source_system or 'TD'}; request_id={request.id}; "
            f"ticket_id={request.external_ticket_id or ''}; requester={request.requester_username}"
        ),
    }

    if request.partition_type == "GPU":
        payload["node_count"] = {"set": True, "infinite": False, "number": request.requested_gpu_nodes}
    else:
        # slurmrestd v0.0.44는 tres를 문자열이 아니라 리스트(TRES 객체 목록)로 요구한다.
        # mem은 Slurm TRES 기준 MB 단위이므로 GB → MB(×1024)로 변환한다.
        tres_list: list[dict[str, object]] = []
        if request.requested_cpu_cores is not None:
            tres_list.append({"type": "cpu", "count": request.requested_cpu_cores})
        if request.requested_memory_gb is not None:
            tres_list.append({"type": "mem", "count": request.requested_memory_gb * 1024})
        if tres_list:
            payload["tres"] = tres_list
        # 정책 확정 전까지 GENERAL/BIGMEM 예약은 기본 1 node로 요청한다.
        payload["node_count"] = {"set": True, "infinite": False, "number": 1}

    return payload


def _find_existing_request(db: Session, payload: object) -> ResourceReservationRequest | None:
    if not isinstance(payload, dict):
        return None

    source_system = _blank_to_none(_raw_text(payload.get("sourceSystem")))
    external_ticket_id = _blank_to_none(_raw_text(payload.get("externalTicketId")))
    idempotency_key = _blank_to_none(_raw_text(payload.get("idempotencyKey")))
    conditions = []
    if source_system and external_ticket_id:
        conditions.append(
            (ResourceReservationRequest.source_system == source_system)
            & (ResourceReservationRequest.external_ticket_id == external_ticket_id)
        )
    if idempotency_key:
        conditions.append(ResourceReservationRequest.idempotency_key == idempotency_key)
    if not conditions:
        return None

    statement = select(ResourceReservationRequest).where(or_(*conditions)).order_by(ResourceReservationRequest.id.asc())
    return db.execute(statement).scalars().first()


def _build_request(payload: object) -> ResourceReservationRequest:
    data = payload if isinstance(payload, dict) else {}
    schedule = data.get("schedule") if isinstance(data.get("schedule"), dict) else {}
    messages: list[str] = []

    source_system = _blank_to_none(_raw_text(data.get("sourceSystem")))
    external_ticket_id = _blank_to_none(_raw_text(data.get("externalTicketId")))
    idempotency_key = _blank_to_none(_raw_text(data.get("idempotencyKey")))
    requester_username = _required_text(data.get("requesterUsername"), "requesterUsername", messages)
    notification_email = _required_text(data.get("notificationEmail"), "notificationEmail", messages)
    title = _required_text(data.get("title"), "title", messages)
    detail = _raw_text(data.get("detail"))

    raw_partition_label = _required_text(data.get("partitionLabel"), "partitionLabel", messages)
    partition_type, slurm_partition = _map_partition(raw_partition_label)
    if raw_partition_label and not partition_type:
        messages.append("partitionLabel을 Slurm partition으로 매핑할 수 없습니다.")

    raw_cpu_cores = _raw_text(data.get("requestedCpuCores"))
    raw_memory_gb = _raw_text(data.get("requestedMemoryGb"))
    raw_gpu_nodes = _raw_text(data.get("requestedGpuNodes"))
    requested_cpu_cores = _parse_optional_int(raw_cpu_cores, "requestedCpuCores", messages)
    requested_memory_gb = _parse_optional_int(raw_memory_gb, "requestedMemoryGb", messages)
    requested_gpu_nodes = _parse_optional_int(raw_gpu_nodes, "requestedGpuNodes", messages)
    _validate_requested_resource(
        partition_type=partition_type,
        raw_cpu_cores=raw_cpu_cores,
        raw_memory_gb=raw_memory_gb,
        raw_gpu_nodes=raw_gpu_nodes,
        requested_cpu_cores=requested_cpu_cores,
        requested_memory_gb=requested_memory_gb,
        requested_gpu_nodes=requested_gpu_nodes,
        messages=messages,
    )

    raw_year = _raw_text(schedule.get("year"))
    raw_month = _raw_text(schedule.get("month"))
    raw_day = _raw_text(schedule.get("day"))
    raw_hour = _raw_text(schedule.get("hour"))
    raw_minute = _raw_text(schedule.get("minute"))
    raw_duration_text = _raw_text(schedule.get("durationText"))
    year = _parse_required_int(raw_year, "schedule.year", messages)
    month = _parse_required_int(raw_month, "schedule.month", messages)
    day = _parse_required_int(raw_day, "schedule.day", messages)
    hour = _parse_required_int(raw_hour, "schedule.hour", messages)
    minute = _parse_required_int(raw_minute, "schedule.minute", messages)
    duration_minutes = _parse_duration_minutes(raw_duration_text)
    if duration_minutes is None:
        messages.append("schedule.durationText를 분 단위로 파싱할 수 없습니다.")

    start_at = _build_start_at(year, month, day, hour, minute, messages)
    end_at = start_at + timedelta(minutes=duration_minutes) if start_at and duration_minutes is not None else None
    if start_at is None or end_at is None:
        messages.append("startAt/endAt을 계산할 수 없습니다.")

    if not isinstance(payload, dict):
        messages.append("요청 JSON은 object 형식이어야 합니다.")

    validation_status = VALIDATION_ERROR if messages else VALIDATION_OK
    status = STATUS_VALIDATION_FAILED if validation_status == VALIDATION_ERROR else STATUS_PENDING_APPROVAL

    return ResourceReservationRequest(
        source_system=source_system,
        external_ticket_id=external_ticket_id,
        idempotency_key=idempotency_key,
        requester_username=requester_username,
        notification_email=notification_email,
        title=title,
        detail=detail,
        raw_payload_json=payload,
        raw_partition_label=raw_partition_label,
        partition_type=partition_type,
        slurm_partition=slurm_partition,
        raw_cpu_cores=raw_cpu_cores,
        raw_memory_gb=raw_memory_gb,
        raw_gpu_nodes=raw_gpu_nodes,
        requested_cpu_cores=requested_cpu_cores,
        requested_memory_gb=requested_memory_gb,
        requested_gpu_nodes=requested_gpu_nodes,
        raw_year=raw_year,
        raw_month=raw_month,
        raw_day=raw_day,
        raw_hour=raw_hour,
        raw_minute=raw_minute,
        raw_duration_text=raw_duration_text,
        start_at=start_at,
        end_at=end_at,
        duration_minutes=duration_minutes,
        status=status,
        validation_status=validation_status,
        validation_messages_json=messages,
    )


def _get_request_or_raise(db: Session, request_id: int) -> ResourceReservationRequest:
    request = db.get(ResourceReservationRequest, request_id)
    if request is None:
        raise LookupError("예약 요청을 찾을 수 없습니다.")
    return request


def _apply_slurm_payload(
    db: Session,
    request: ResourceReservationRequest,
    *,
    success_message: str,
) -> ResourceReservationActionResponse:
    payload = request.slurm_payload_json if isinstance(request.slurm_payload_json, dict) else build_slurm_reservation_payload(request)
    result = create_or_update_slurm_reservation(payload)
    now = datetime.now(timezone.utc)
    request.slurm_response_json = result.response_json
    request.updated_at = now

    if result.success:
        request.status = STATUS_SLURM_RESERVED
        request.slurm_error = None
        db.commit()
        db.refresh(request)
        return ResourceReservationActionResponse(
            success=True,
            status=request.status,
            requestId=str(request.id),
            slurmReservationName=request.slurm_reservation_name,
            message=success_message,
        )

    request.status = STATUS_SLURM_APPLY_FAILED
    request.slurm_error = result.error or "Slurm 예약 생성에 실패했습니다."
    db.commit()
    db.refresh(request)
    return ResourceReservationActionResponse(
        success=False,
        status=request.status,
        requestId=str(request.id),
        slurmReservationName=request.slurm_reservation_name,
        message="Slurm 예약 생성에 실패했습니다.",
        slurmError=request.slurm_error,
    )


def _to_list_item(request: ResourceReservationRequest) -> ResourceReservationRequestResponse:
    return ResourceReservationRequestResponse(
        id=str(request.id),
        externalTicketId=request.external_ticket_id or "",
        status=request.status,
        validationStatus=request.validation_status,
        validationMessages=_as_string_list(request.validation_messages_json),
        title=request.title or "",
        detail=request.detail or "",
        requesterUsername=request.requester_username or "",
        requesterEmail=request.notification_email,
        partitionType=request.partition_type,
        slurmPartition=request.slurm_partition,
        requestedCpuCores=request.requested_cpu_cores,
        requestedMemoryGb=request.requested_memory_gb,
        requestedGpuNodes=request.requested_gpu_nodes,
        startAt=to_kst_iso_business(request.start_at),
        endAt=to_kst_iso_business(request.end_at),
        durationText=request.raw_duration_text or "",
        durationMinutes=request.duration_minutes,
        slurmReservationName=request.slurm_reservation_name,
        slurmPayloadPreview=request.slurm_payload_json,
        adminMemo=request.admin_memo,
        rejectionReason=request.rejection_reason,
        approvedBy=request.approved_by,
        approvedAt=to_kst_iso_system(request.approved_at),
        rejectedBy=request.rejected_by,
        rejectedAt=to_kst_iso_system(request.rejected_at),
        slurmError=request.slurm_error,
        createdAt=to_kst_iso_system(request.created_at) or "",
        updatedAt=to_kst_iso_system(request.updated_at) or "",
        auditLogs=_build_audit_logs(request),
    )


def _build_audit_logs(request: ResourceReservationRequest) -> list[ReservationAuditLogResponse]:
    logs = [
        ReservationAuditLogResponse(
            action="SUBMITTED",
            actor=request.source_system or "TD",
            message="외부 티켓으로 예약 요청이 접수되었습니다.",
            createdAt=to_kst_iso_system(request.created_at) or "",
        )
    ]
    for message in _as_string_list(request.validation_messages_json):
        if request.validation_status == VALIDATION_ERROR:
            action = "VALIDATION_FAILED"
        else:
            action = "VALIDATION_WARNING"
        logs.append(
            ReservationAuditLogResponse(
                action=action,
                actor="Insight",
                message=message,
                createdAt=to_kst_iso_system(request.updated_at) or "",
            )
        )
    if request.approved_at:
        logs.append(
            ReservationAuditLogResponse(
                action="APPROVED",
                actor=request.approved_by or "admin",
                message="관리자가 예약 요청을 승인했습니다.",
                createdAt=to_kst_iso_system(request.approved_at) or "",
            )
        )
    if request.status == STATUS_SLURM_RESERVED:
        logs.append(
            ReservationAuditLogResponse(
                action="SLURM_RESERVED",
                actor="Insight",
                message="Slurm 예약 생성이 완료되었습니다.",
                createdAt=to_kst_iso_system(request.updated_at) or "",
            )
        )
    if request.status == STATUS_SLURM_APPLY_FAILED:
        logs.append(
            ReservationAuditLogResponse(
                action="SLURM_APPLY_FAILED",
                actor="Insight",
                message=request.slurm_error or "Slurm 예약 생성에 실패했습니다.",
                createdAt=to_kst_iso_system(request.updated_at) or "",
            )
        )
    if request.rejected_at:
        logs.append(
            ReservationAuditLogResponse(
                action="REJECTED",
                actor=request.rejected_by or "admin",
                message=request.rejection_reason or "관리자가 예약 요청을 거절했습니다.",
                createdAt=to_kst_iso_system(request.rejected_at) or "",
            )
        )
    return logs


def _as_string_list(value: object | None) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def _validate_for_slurm_payload(request: ResourceReservationRequest) -> list[str]:
    errors: list[str] = []
    if not request.requester_username:
        errors.append("requester_username이 없습니다.")
    if not request.slurm_partition:
        errors.append("slurm_partition이 없습니다.")
    if not request.partition_type:
        errors.append("partition_type이 없습니다.")
    if request.start_at is None:
        errors.append("start_at이 없습니다.")
    if request.duration_minutes is None:
        errors.append("duration_minutes가 없습니다.")
    if request.partition_type == "GPU" and request.requested_gpu_nodes is None:
        errors.append("GPU 요청에는 requested_gpu_nodes가 필요합니다.")
    if request.partition_type in {"GENERAL", "BIGMEM"} and request.requested_cpu_cores is None and request.requested_memory_gb is None:
        errors.append("GENERAL/BIGMEM 요청에는 requested_cpu_cores 또는 requested_memory_gb가 필요합니다.")
    return errors


def _safe_slurm_reservation_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())
    return sanitized or "insight-rsv"


def _raw_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value


def _required_text(value: object, field_name: str, messages: list[str]) -> str | None:
    text = _raw_text(value)
    if text is None or not text.strip():
        messages.append(f"{field_name}은 필수입니다.")
        return text
    return text


def _parse_required_int(value: str | None, field_name: str, messages: list[str]) -> int | None:
    if value is None or not value.strip():
        messages.append(f"{field_name}은 필수 정수 값입니다.")
        return None
    try:
        return int(value.strip())
    except ValueError:
        messages.append(f"{field_name}을 정수로 파싱할 수 없습니다.")
        return None


def _parse_optional_int(value: str | None, field_name: str, messages: list[str]) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError:
        messages.append(f"{field_name}을 정수로 파싱할 수 없습니다.")
        return None


def _map_partition(label: str | None) -> tuple[str | None, str | None]:
    """OOD partitionLabel("GPU"/"General"/"BigMem")을 (자원 유형, Slurm 파티션 이름)으로 변환한다.

    현재 실제 Slurm 파티션은 bridge_1 단일이라 세 라벨 모두 bridge_1로 보낸다.
    Slurm 파티션이 늘어나면 아래 매핑의 두 번째 값만 바꾸면 된다.
    (자원 유형 GENERAL/BIGMEM/GPU 구분은 자원 필드 매핑/검증용으로 유지한다.)
    """
    if not label:
        return None, None
    normalized = label.lower()
    if "일반" in label or "general" in normalized:
        return "GENERAL", "bridge_1"
    if "대용량" in label or "bigmem" in normalized:
        return "BIGMEM", "bridge_1"
    if "gpu" in normalized:
        return "GPU", "bridge_1"
    return None, None


def _validate_requested_resource(
    *,
    partition_type: str | None,
    raw_cpu_cores: str | None,
    raw_memory_gb: str | None,
    raw_gpu_nodes: str | None,
    requested_cpu_cores: int | None,
    requested_memory_gb: int | None,
    requested_gpu_nodes: int | None,
    messages: list[str],
) -> None:
    if partition_type == "GPU":
        if raw_gpu_nodes is None or not raw_gpu_nodes.strip():
            messages.append("GPU partition은 requestedGpuNodes가 필요합니다.")
        elif requested_gpu_nodes is None:
            messages.append("GPU partition의 requestedGpuNodes를 파싱할 수 없습니다.")
        return

    if partition_type in {"GENERAL", "BIGMEM"}:
        has_cpu = raw_cpu_cores is not None and raw_cpu_cores.strip()
        has_memory = raw_memory_gb is not None and raw_memory_gb.strip()
        if not has_cpu and not has_memory:
            messages.append("GENERAL/BIGMEM partition은 requestedMemoryGb 또는 requestedCpuCores가 필요합니다.")
        elif requested_cpu_cores is None and requested_memory_gb is None:
            messages.append("GENERAL/BIGMEM partition의 requestedMemoryGb 또는 requestedCpuCores를 파싱할 수 없습니다.")


def _parse_duration_minutes(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip().lower()
    if not text:
        return None

    total = 0
    matched_spans: list[tuple[int, int]] = []
    for match in re.finditer(r"(\d+)\s*([dh])", text):
        amount = int(match.group(1))
        unit = match.group(2)
        total += amount * 1440 if unit == "d" else amount * 60
        matched_spans.append(match.span())

    if not matched_spans:
        return None

    remainder = text
    for start, end in reversed(matched_spans):
        remainder = remainder[:start] + remainder[end:]
    if remainder.strip():
        return None
    return total


def _build_start_at(
    year: int | None,
    month: int | None,
    day: int | None,
    hour: int | None,
    minute: int | None,
    messages: list[str],
) -> datetime | None:
    if None in {year, month, day, hour, minute}:
        return None
    try:
        return parse_td_schedule_as_kst(year, month, day, hour, minute)
    except ValueError as exc:
        messages.append(f"schedule 날짜/시간 값이 유효하지 않습니다: {exc}")
        return None
