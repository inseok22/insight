from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AdminBase


class ResourceReservationRequest(AdminBase):
    __tablename__ = "resource_reservation_requests"
    __table_args__ = (
        UniqueConstraint("source_system", "external_ticket_id", name="uq_resource_reservation_source_ticket"),
        UniqueConstraint("idempotency_key", name="uq_resource_reservation_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_system: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_ticket_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    requester_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    raw_partition_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partition_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    slurm_partition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_cpu_cores: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_memory_gb: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_gpu_nodes: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_memory_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_gpu_nodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_month: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_day: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_hour: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_minute: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_duration_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    validation_messages_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    slurm_reservation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slurm_payload_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    slurm_response_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    slurm_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
