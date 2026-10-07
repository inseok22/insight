export type ReservationStatus = 'RUNNING' | 'UPCOMING' | 'ENDED' | 'ERROR';
export type ReservationSource = 'INSIGHT' | 'SLURM_MANUAL';
export type PartitionType = 'GENERAL' | 'BIGMEM' | 'GPU';

export interface ResourceReservation {
  id: string;
  reservationName: string;
  displayStatus: ReservationStatus;
  source: ReservationSource;
  externalTicketId: string | null;
  title: string;
  requesterUsername: string;
  requesterEmail: string | null;
  users: string[];
  partitionType: PartitionType;
  slurmPartition: string;
  startAt: string;
  endAt: string;
  durationText: string;
  cpuCores: number | null;
  memoryGb: number | null;
  gpuNodeCount: number | null;
  nodeList: string | null;
  tres: string | null;
  comment: string | null;
  slurmExists: boolean;
  insightRequestExists: boolean;
  lastSyncedAt: string | null;
}

export interface ResourceReservationListResponse {
  generatedAt: string;
  items: ResourceReservation[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchResourceReservations(): Promise<ResourceReservationListResponse> {
  const url = `${API_BASE_URL}/api/admin/resource/reservations`;

  // 프론트엔드는 Slurm GET /slurm/v0.0.44/reservations/ 를 직접 호출하지 않습니다.
  // Insight Backend가 Slurm API를 호출하고, 프론트는 위의 Insight API만 조회합니다.
  // 상태 판단 기준(백엔드에서 계산):
  // RUNNING: 현재 시간이 startAt 이상, endAt 미만.
  // UPCOMING: 현재 시간이 startAt 이전.
  // ENDED: 현재 시간이 endAt 이후. (Slurm은 종료 후 purge될 수 있어 목록에서 빠질 수 있음)
  // ERROR: reservationName 누락, startAt/endAt 파싱 실패 등.
  const response = await fetch(url, {
    headers: getAuthHeader(),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || '자원 예약 정보를 조회하지 못했습니다.');
  }

  return response.json();
}
