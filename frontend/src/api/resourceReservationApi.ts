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

export async function fetchResourceReservations(): Promise<ResourceReservationListResponse> {
  const useDummy = import.meta.env.VITE_USE_DUMMY_RESERVATIONS !== 'false';
  const url = useDummy
    ? `/mocks/slurm-reservations.dummy.json?t=${Date.now()}`
    : '/api/admin/resource/reservations';

  // 프론트엔드는 Slurm GET /slurm/v0.0.44/reservations/ 를 직접 호출하지 않습니다.
  // 실제 연동 시 Insight Backend가 Slurm API를 호출하고, 프론트는 위의 Insight API만 조회합니다.
  // 상태 판단 기준:
  // RUNNING: slurmExists=true 이고 현재 시간이 startAt 이상, endAt 미만.
  // UPCOMING: slurmExists=true 이고 현재 시간이 startAt 이전.
  // ENDED: 현재 시간이 endAt 이후이고 Insight DB 또는 더미 데이터에 예약 이력이 남아 있는 경우.
  //        Slurm reservation은 종료 후 자동 purge될 수 있으므로 slurmExists=false 여도 정상입니다.
  // ERROR: 아직 종료되지 않은 예약인데 slurmExists=false, reservationName 누락,
  //        startAt/endAt 파싱 실패, 필수 데이터 누락, Slurm API 조회 실패 또는 비정상 응답.
  //        단, SLURM_MANUAL 이고 현재 Slurm에 존재하는 예약은 Insight 요청이 없어도 정상입니다.
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error('자원 예약 정보를 조회하지 못했습니다.');
  }

  return response.json();
}
