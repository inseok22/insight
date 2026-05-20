export type ReservationRequestStatus =
  | 'PENDING_APPROVAL'
  | 'VALIDATION_FAILED'
  | 'APPLYING_TO_SLURM'
  | 'SLURM_RESERVED'
  | 'SLURM_APPLY_FAILED'
  | 'REJECTED';

export type ValidationStatus = 'OK' | 'WARNING' | 'ERROR';
export type PartitionType = 'GENERAL' | 'BIGMEM' | 'GPU';

export interface ReservationAuditLog {
  action: string;
  actor: string;
  message: string;
  createdAt: string;
}

export interface SlurmPayloadPreview {
  name?: string;
  users?: string[];
  partition?: string;
  node_count?: {
    set: boolean;
    number: number;
  };
  tres?: string;
  comment?: string;
  [key: string]: unknown;
}

export interface ResourceReservationRequest {
  id: string;
  externalTicketId: string;
  status: ReservationRequestStatus;
  validationStatus: ValidationStatus;
  validationMessages: string[];
  title: string;
  detail: string;
  requesterUsername: string;
  requesterEmail: string | null;
  partitionType: PartitionType | null;
  slurmPartition: string | null;
  requestedCpuCores: number | null;
  requestedMemoryGb: number | null;
  requestedGpuNodes: number | null;
  startAt: string | null;
  endAt: string | null;
  durationText: string;
  durationMinutes: number | null;
  slurmReservationName: string | null;
  slurmPayloadPreview: SlurmPayloadPreview | null;
  adminMemo: string | null;
  rejectionReason: string | null;
  approvedBy: string | null;
  approvedAt: string | null;
  rejectedBy: string | null;
  rejectedAt: string | null;
  slurmError: string | null;
  createdAt: string;
  updatedAt: string;
  auditLogs: ReservationAuditLog[];
}

export interface ResourceReservationRequestListResponse {
  generatedAt: string;
  items: ResourceReservationRequest[];
}

export interface ResourceReservationActionResponse {
  success: boolean;
  status: ReservationRequestStatus;
  requestId: string;
  message: string;
  slurmReservationName?: string | null;
  slurmError?: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function isUsingDummyReservationRequests() {
  return import.meta.env.VITE_USE_DUMMY_RESERVATION_REQUESTS === 'true';
}

export async function fetchResourceReservationRequests(): Promise<ResourceReservationRequestListResponse> {
  const useDummy = isUsingDummyReservationRequests();
  const url = useDummy
    ? `/mocks/resource-reservation-requests.dummy.json?t=${Date.now()}`
    : `${API_BASE_URL}/api/admin/resource/reservation-requests`;

  const response = await fetch(url, {
    headers: useDummy ? undefined : { ...getAuthHeader() },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || '자원 예약 요청 정보를 조회하지 못했습니다.');
  }

  return response.json();
}

export async function approveResourceReservationRequest(
  requestId: string,
  adminMemo?: string,
): Promise<ResourceReservationActionResponse> {
  return postReservationAction(`${requestId}/approve`, { adminMemo });
}

export async function rejectResourceReservationRequest(
  requestId: string,
  rejectionReason: string,
): Promise<ResourceReservationActionResponse> {
  return postReservationAction(`${requestId}/reject`, { rejectionReason });
}

export async function retrySlurmReservationRequest(
  requestId: string,
  adminMemo?: string,
): Promise<ResourceReservationActionResponse> {
  return postReservationAction(`${requestId}/retry-slurm`, { adminMemo });
}

async function postReservationAction(path: string, body: object): Promise<ResourceReservationActionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/resource/reservation-requests/${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.detail || '예약 요청 처리 중 오류가 발생했습니다.');
  }

  return data as ResourceReservationActionResponse;
}
