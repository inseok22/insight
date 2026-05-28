import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Row,
  Col,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  fetchResourceReservations,
  type PartitionType,
  type ReservationSource,
  type ReservationStatus,
  type ResourceReservation,
  type ResourceReservationListResponse,
} from '../../../api/resourceReservationApi';
import { formatKstDateTime } from '../../../utils/time';
import './ResourceReservationPage.css';

type StatusFilter = ReservationStatus | 'ALL';
type PartitionFilter = PartitionType | 'ALL';
type SourceFilter = ReservationSource | 'ALL';

const isUsingDummyReservations = import.meta.env.VITE_USE_DUMMY_RESERVATIONS === 'true';

const statusLabels: Record<ReservationStatus, string> = {
  RUNNING: '진행 중',
  UPCOMING: '예정',
  ENDED: '종료',
  ERROR: '오류',
};

const statusColors: Record<ReservationStatus, string> = {
  RUNNING: 'green',
  UPCOMING: 'blue',
  ENDED: 'default',
  ERROR: 'red',
};

const sourceLabels: Record<ReservationSource, string> = {
  INSIGHT: 'Insight',
  SLURM_MANUAL: 'Slurm 수동',
};

const partitionLabels: Record<PartitionType, string> = {
  GENERAL: 'General',
  BIGMEM: 'BigMem',
  GPU: 'GPU',
};

function renderStatusTag(status: ReservationStatus) {
  return <Tag color={statusColors[status]}>{statusLabels[status]}</Tag>;
}

function renderSourceTag(source: ReservationSource) {
  return <Tag>{sourceLabels[source]}</Tag>;
}

function formatResource(record: ResourceReservation) {
  if (record.partitionType === 'GPU' && record.gpuNodeCount !== null) {
    return `GPU Node ${record.gpuNodeCount}`;
  }

  if (record.cpuCores !== null && record.memoryGb !== null) {
    return `${record.cpuCores}C / ${record.memoryGb}GB`;
  }

  if (record.cpuCores !== null) {
    return `${record.cpuCores}C`;
  }

  if (record.memoryGb !== null) {
    return `${record.memoryGb}GB`;
  }

  return '-';
}

function valueOrDash(value?: string | number | null) {
  if (value === null || value === undefined || value === '') return '-';
  return value;
}

function booleanLabel(value: boolean) {
  return value ? '예' : '아니오';
}

export default function ResourceReservationLookupTab() {
  const [data, setData] = useState<ResourceReservationListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [partitionFilter, setPartitionFilter] = useState<PartitionFilter>('ALL');
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('ALL');
  const [searchText, setSearchText] = useState('');
  const [selectedReservation, setSelectedReservation] = useState<ResourceReservation | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);

  const loadReservations = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const response = await fetchResourceReservations();
      setData(response);
      setLastFetchedAt(new Date());
    } catch (error) {
      console.error(error);
      setErrorMessage(error instanceof Error ? error.message : '자원 예약 정보를 조회하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReservations();
  }, [loadReservations]);

  const items = useMemo(() => data?.items ?? [], [data]);

  const summary = useMemo(() => ({
    total: items.length,
    running: items.filter((item) => item.displayStatus === 'RUNNING').length,
    upcoming: items.filter((item) => item.displayStatus === 'UPCOMING').length,
    ended: items.filter((item) => item.displayStatus === 'ENDED').length,
    gpu: items.filter((item) => item.partitionType === 'GPU').length,
    error: items.filter((item) => item.displayStatus === 'ERROR').length,
  }), [items]);

  const filteredItems = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();

    return items.filter((item) => {
      if (statusFilter !== 'ALL' && item.displayStatus !== statusFilter) return false;
      if (partitionFilter !== 'ALL' && item.partitionType !== partitionFilter) return false;
      if (sourceFilter !== 'ALL' && item.source !== sourceFilter) return false;
      if (!keyword) return true;

      return [
        item.reservationName,
        item.title,
        item.requesterUsername,
        item.nodeList,
        item.externalTicketId,
      ].some((value) => value?.toLowerCase().includes(keyword));
    });
  }, [items, partitionFilter, searchText, sourceFilter, statusFilter]);

  const resetFilters = () => {
    setStatusFilter('ALL');
    setPartitionFilter('ALL');
    setSourceFilter('ALL');
    setSearchText('');
  };

  const columns: ColumnsType<ResourceReservation> = [
    {
      title: '상태',
      dataIndex: 'displayStatus',
      key: 'displayStatus',
      width: 120,
      render: (value: ReservationStatus) => renderStatusTag(value),
    },
    {
      title: '예약명',
      dataIndex: 'reservationName',
      key: 'reservationName',
      width: 180,
    },
    {
      title: '제목',
      dataIndex: 'title',
      key: 'title',
      width: 180,
    },
    {
      title: '신청자',
      dataIndex: 'requesterUsername',
      key: 'requesterUsername',
      width: 120,
    },
    {
      title: '파티션',
      dataIndex: 'partitionType',
      key: 'partitionType',
      width: 110,
      render: (value: PartitionType) => partitionLabels[value],
    },
    {
      title: '시작 시간',
      dataIndex: 'startAt',
      key: 'startAt',
      width: 180,
      render: (value: string) => formatKstDateTime(value),
    },
    {
      title: '종료 시간',
      dataIndex: 'endAt',
      key: 'endAt',
      width: 180,
      render: (value: string) => formatKstDateTime(value),
    },
    {
      title: '사용 시간',
      dataIndex: 'durationText',
      key: 'durationText',
      width: 100,
    },
    {
      title: '자원',
      key: 'resource',
      width: 140,
      render: (_, record) => formatResource(record),
    },
    {
      title: '노드',
      dataIndex: 'nodeList',
      key: 'nodeList',
      width: 140,
      render: (value: string | null) => valueOrDash(value),
    },
    {
      title: '출처',
      dataIndex: 'source',
      key: 'source',
      width: 120,
      render: (value: ReservationSource) => renderSourceTag(value),
    },
    {
      title: '티켓',
      dataIndex: 'externalTicketId',
      key: 'externalTicketId',
      width: 100,
      render: (value: string | null) => valueOrDash(value),
    },
    {
      title: '상세',
      key: 'detail',
      width: 90,
      fixed: 'right',
      render: (_, record) => (
        <Button
          size="small"
          onClick={(event) => {
            event.stopPropagation();
            setSelectedReservation(record);
          }}
        >
          보기
        </Button>
      ),
    },
  ];

  return (
    <div className="resource-reservation-page">
      <div className="resource-reservation-toolbar">
        <Typography.Text type="secondary">
          Slurm에 등록된 자원 예약 정보를 실시간으로 조회합니다.
        </Typography.Text>
        <Space wrap>
          <Typography.Text type="secondary">
            마지막 조회: {formatKstDateTime(lastFetchedAt, { seconds: true })}
          </Typography.Text>
          {isUsingDummyReservations ? <Tag color="gold">더미 데이터 사용 중</Tag> : null}
          <Button
            loading={loading}
            onClick={() => { void loadReservations(); }}
          >
            {loading ? '조회 중...' : '다시조회'}
          </Button>
        </Space>
      </div>

      {errorMessage ? (
        <Alert type="error" showIcon message={errorMessage} />
      ) : null}

      <Row gutter={[12, 12]} className="resource-reservation-summary">
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">전체 예약</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.total}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">진행 중</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.running}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">예정</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.upcoming}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">종료</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.ended}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">GPU 예약</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.gpu}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">오류</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.error}</span>
          </Card>
        </Col>
      </Row>

      <Card>
        <div className="resource-reservation-filters">
          <Select<StatusFilter>
            className="resource-reservation-filter-select"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'ALL', label: '상태 전체' },
              { value: 'RUNNING', label: '진행 중' },
              { value: 'UPCOMING', label: '예정' },
              { value: 'ENDED', label: '종료' },
              { value: 'ERROR', label: '오류' },
            ]}
          />
          <Select<PartitionFilter>
            className="resource-reservation-filter-select"
            value={partitionFilter}
            onChange={setPartitionFilter}
            options={[
              { value: 'ALL', label: '파티션 전체' },
              { value: 'GENERAL', label: 'General' },
              { value: 'BIGMEM', label: 'BigMem' },
              { value: 'GPU', label: 'GPU' },
            ]}
          />
          <Select<SourceFilter>
            className="resource-reservation-filter-select"
            value={sourceFilter}
            onChange={setSourceFilter}
            options={[
              { value: 'ALL', label: '출처 전체' },
              { value: 'INSIGHT', label: 'Insight' },
              { value: 'SLURM_MANUAL', label: 'Slurm 수동' },
            ]}
          />
          <Input
            className="resource-reservation-search"
            allowClear
            placeholder="예약명, 제목, 신청자, 노드, 티켓 검색"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
          <Button onClick={resetFilters}>초기화</Button>
        </div>
      </Card>

      <div className="resource-reservation-table-wrap">
        <Table<ResourceReservation>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={filteredItems}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 1580 }}
          locale={{ emptyText: <Empty description="조건에 맞는 예약이 없습니다." /> }}
          onRow={(record) => ({
            onClick: () => setSelectedReservation(record),
            style: { cursor: 'pointer' },
          })}
        />
      </div>

      <Drawer
        title="자원 예약 상세"
        open={selectedReservation !== null}
        onClose={() => setSelectedReservation(null)}
        width={720}
      >
        {selectedReservation ? (
          <Descriptions bordered size="small" column={1} className="resource-reservation-detail-list">
            <Descriptions.Item label="예약명">{selectedReservation.reservationName}</Descriptions.Item>
            <Descriptions.Item label="상태">{renderStatusTag(selectedReservation.displayStatus)}</Descriptions.Item>
            <Descriptions.Item label="출처">{renderSourceTag(selectedReservation.source)}</Descriptions.Item>
            <Descriptions.Item label="외부 티켓 ID">{valueOrDash(selectedReservation.externalTicketId)}</Descriptions.Item>
            <Descriptions.Item label="신청자">{selectedReservation.requesterUsername}</Descriptions.Item>
            <Descriptions.Item label="이메일">{valueOrDash(selectedReservation.requesterEmail)}</Descriptions.Item>
            <Descriptions.Item label="Slurm partition">{selectedReservation.slurmPartition}</Descriptions.Item>
            <Descriptions.Item label="사용자 목록">{selectedReservation.users.join(', ') || '-'}</Descriptions.Item>
            <Descriptions.Item label="시작 시간">{formatKstDateTime(selectedReservation.startAt)}</Descriptions.Item>
            <Descriptions.Item label="종료 시간">{formatKstDateTime(selectedReservation.endAt)}</Descriptions.Item>
            <Descriptions.Item label="사용 시간">{selectedReservation.durationText}</Descriptions.Item>
            <Descriptions.Item label="CPU">{valueOrDash(selectedReservation.cpuCores)}</Descriptions.Item>
            <Descriptions.Item label="Memory">{selectedReservation.memoryGb !== null ? `${selectedReservation.memoryGb}GB` : '-'}</Descriptions.Item>
            <Descriptions.Item label="GPU Node">{valueOrDash(selectedReservation.gpuNodeCount)}</Descriptions.Item>
            <Descriptions.Item label="Node List">{valueOrDash(selectedReservation.nodeList)}</Descriptions.Item>
            <Descriptions.Item label="TRES">{valueOrDash(selectedReservation.tres)}</Descriptions.Item>
            <Descriptions.Item label="Comment">{valueOrDash(selectedReservation.comment)}</Descriptions.Item>
            <Descriptions.Item label="Slurm 존재 여부">{booleanLabel(selectedReservation.slurmExists)}</Descriptions.Item>
            <Descriptions.Item label="Insight 요청 존재 여부">{booleanLabel(selectedReservation.insightRequestExists)}</Descriptions.Item>
            <Descriptions.Item label="마지막 동기화 시간">{formatKstDateTime(selectedReservation.lastSyncedAt)}</Descriptions.Item>
          </Descriptions>
        ) : null}
      </Drawer>
    </div>
  );
}
