import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  approveResourceReservationRequest,
  fetchResourceReservationRequests,
  isUsingDummyReservationRequests,
  rejectResourceReservationRequest,
  retrySlurmReservationRequest,
  type PartitionType,
  type ReservationAuditLog,
  type ReservationRequestStatus,
  type ResourceReservationRequest,
  type ValidationStatus,
} from '../../../api/resourceReservationRequestApi';
import { formatKstDateTime } from '../../../utils/time';
import './ResourceReservationPage.css';

type RequestStatusFilter = ReservationRequestStatus | 'OPEN' | 'ALL';
type PartitionFilter = PartitionType | 'ALL';
type ValidationFilter = ValidationStatus | 'ALL';
type ActionType = 'approve' | 'reject' | 'retry';

const statusLabels: Record<ReservationRequestStatus, string> = {
  PENDING_APPROVAL: '승인 대기',
  VALIDATION_FAILED: '검증 실패',
  APPLYING_TO_SLURM: 'Slurm 반영 중',
  SLURM_RESERVED: '예약 완료',
  SLURM_APPLY_FAILED: 'Slurm 반영 실패',
  REJECTED: '거절',
};

const statusColors: Record<ReservationRequestStatus, string> = {
  PENDING_APPROVAL: 'gold',
  VALIDATION_FAILED: 'red',
  APPLYING_TO_SLURM: 'blue',
  SLURM_RESERVED: 'green',
  SLURM_APPLY_FAILED: 'red',
  REJECTED: 'default',
};

const validationLabels: Record<ValidationStatus, string> = {
  OK: '정상',
  WARNING: '경고',
  ERROR: '오류',
};

const validationColors: Record<ValidationStatus, string> = {
  OK: 'green',
  WARNING: 'gold',
  ERROR: 'red',
};

const partitionLabels: Record<PartitionType, string> = {
  GENERAL: 'General',
  BIGMEM: 'BigMem',
  GPU: 'GPU',
};

function valueOrDash(value?: string | number | null) {
  if (value === null || value === undefined || value === '') return '-';
  return value;
}

function renderStatusTag(status: ReservationRequestStatus) {
  return <Tag color={statusColors[status]}>{statusLabels[status]}</Tag>;
}

function renderValidationTag(status: ValidationStatus) {
  return <Tag color={validationColors[status]}>{validationLabels[status]}</Tag>;
}

function formatRequestedResource(record: ResourceReservationRequest) {
  if (record.partitionType === 'GPU' && record.requestedGpuNodes !== null) {
    return `GPU Node ${record.requestedGpuNodes}`;
  }

  if (record.requestedCpuCores !== null && record.requestedMemoryGb !== null) {
    return `${record.requestedCpuCores}C / ${record.requestedMemoryGb}GB`;
  }

  if (record.requestedCpuCores !== null) return `${record.requestedCpuCores}C`;
  if (record.requestedMemoryGb !== null) return `${record.requestedMemoryGb}GB`;
  return '-';
}

function createAuditLog(action: string, actor: string, message: string, createdAt: string): ReservationAuditLog {
  return { action, actor, message, createdAt };
}

export default function ResourceReservationApprovalTab() {
  const useDummy = isUsingDummyReservationRequests();
  const { modal, message: messageApi } = App.useApp();
  const [rows, setRows] = useState<ResourceReservationRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingKey, setActionLoadingKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RequestStatusFilter>('OPEN');
  const [partitionFilter, setPartitionFilter] = useState<PartitionFilter>('ALL');
  const [validationFilter, setValidationFilter] = useState<ValidationFilter>('ALL');
  const [searchText, setSearchText] = useState('');
  const [lastFetchedAt, setLastFetchedAt] = useState<Date | null>(null);
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);

  const selectedRequest = useMemo(
    () => rows.find((row) => row.id === selectedRequestId) ?? null,
    [rows, selectedRequestId],
  );

  const loadRequests = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const response = await fetchResourceReservationRequests();
      setRows(response.items);
      setLastFetchedAt(new Date());
    } catch (error) {
      console.error(error);
      setErrorMessage(error instanceof Error ? error.message : '자원 예약 요청 정보를 조회하지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  const summary = useMemo(() => ({
    total: rows.length,
    pending: rows.filter((item) => item.status === 'PENDING_APPROVAL').length,
    validationFailed: rows.filter((item) => item.status === 'VALIDATION_FAILED').length,
    slurmFailed: rows.filter((item) => item.status === 'SLURM_APPLY_FAILED').length,
    reserved: rows.filter((item) => item.status === 'SLURM_RESERVED').length,
    rejected: rows.filter((item) => item.status === 'REJECTED').length,
  }), [rows]);

  const filteredRows = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();

    return rows.filter((item) => {
      if (statusFilter === 'OPEN' && !['PENDING_APPROVAL', 'VALIDATION_FAILED', 'SLURM_APPLY_FAILED'].includes(item.status)) return false;
      if (statusFilter !== 'OPEN' && statusFilter !== 'ALL' && item.status !== statusFilter) return false;
      if (partitionFilter !== 'ALL' && item.partitionType !== partitionFilter) return false;
      if (validationFilter !== 'ALL' && item.validationStatus !== validationFilter) return false;
      if (!keyword) return true;

      return [
        item.externalTicketId,
        item.title,
        item.requesterUsername,
        item.requesterEmail,
        item.slurmReservationName,
      ].some((value) => value?.toLowerCase().includes(keyword));
    });
  }, [partitionFilter, rows, searchText, statusFilter, validationFilter]);

  const resetFilters = () => {
    setStatusFilter('OPEN');
    setPartitionFilter('ALL');
    setValidationFilter('ALL');
    setSearchText('');
  };

  const updateRequest = (
    requestId: string,
    updater: (request: ResourceReservationRequest) => ResourceReservationRequest,
  ) => {
    setRows((prevRows) => prevRows.map((row) => (row.id === requestId ? updater(row) : row)));
  };

  const runAction = async (requestId: string, actionType: ActionType, action: () => Promise<void>) => {
    const key = `${actionType}:${requestId}`;
    try {
      setActionLoadingKey(key);
      setErrorMessage(null);
      await action();
    } catch (error) {
      console.error(error);
      const fallback = '예약 요청 처리 중 오류가 발생했습니다.';
      const messageText = error instanceof Error ? error.message : fallback;
      setErrorMessage(messageText);
      messageApi.error(messageText);
    } finally {
      setActionLoadingKey(null);
    }
  };

  const approveRequest = (record: ResourceReservationRequest) => {
    modal.confirm({
      title: '예약 요청 승인',
      content: (
        <Typography.Text style={{ whiteSpace: 'pre-line' }}>
          {`이 예약 요청을 승인하고 Slurm 예약 생성을 진행하시겠습니까?\n티켓 ID: ${record.externalTicketId}\n제목: ${record.title}`}
        </Typography.Text>
      ),
      okText: '승인',
      cancelText: '취소',
      onOk: async () => {
        if (!useDummy) {
          await runAction(record.id, 'approve', async () => {
            const result = await approveResourceReservationRequest(record.id);
            if (result.success) {
              messageApi.success(result.message);
            } else {
              messageApi.error(result.slurmError || result.message);
            }
            await loadRequests();
          });
          return;
        }

        const approvedAt = new Date().toISOString();

        // Slurm에는 별도 승인/거절 API가 없습니다. 실제 연동 시 프론트는 Insight 승인 API만 호출하고,
        // 백엔드가 POST /slurm/v0.0.44/reservation 으로 Slurm 예약 생성을 수행합니다.
        updateRequest(record.id, (request) => ({
          ...request,
          status: 'APPLYING_TO_SLURM',
          approvedBy: 'admin',
          approvedAt,
          updatedAt: approvedAt,
          auditLogs: [
            ...request.auditLogs,
            createAuditLog('APPROVED', 'admin', '관리자가 예약 요청을 승인했습니다.', approvedAt),
          ],
        }));

        window.setTimeout(() => {
          const reservedAt = new Date().toISOString();
          updateRequest(record.id, (request) => ({
            ...request,
            status: 'SLURM_RESERVED',
            slurmReservationName: request.slurmReservationName || `insight-rsv-${request.id}`,
            slurmError: null,
            updatedAt: reservedAt,
            auditLogs: [
              ...request.auditLogs,
              createAuditLog('SLURM_RESERVED', 'Insight', 'Slurm 예약 생성이 완료되었습니다.', reservedAt),
            ],
          }));
        }, 650);
      },
    });
  };

  const rejectRequest = (record: ResourceReservationRequest) => {
    const reason = window.prompt('거절 사유를 입력하세요.');
    if (!reason?.trim()) return;

    if (!useDummy) {
      void runAction(record.id, 'reject', async () => {
        const result = await rejectResourceReservationRequest(record.id, reason.trim());
        messageApi.success(result.message);
        await loadRequests();
      });
      return;
    }

    const rejectedAt = new Date().toISOString();
    updateRequest(record.id, (request) => ({
      ...request,
      status: 'REJECTED',
      rejectionReason: reason.trim(),
      rejectedBy: 'admin',
      rejectedAt,
      updatedAt: rejectedAt,
      auditLogs: [
        ...request.auditLogs,
        createAuditLog('REJECTED', 'admin', '관리자가 예약 요청을 거절했습니다.', rejectedAt),
      ],
    }));
  };

  const retrySlurm = (record: ResourceReservationRequest) => {
    modal.confirm({
      title: 'Slurm 반영 재시도',
      content: (
        <Typography.Text style={{ whiteSpace: 'pre-line' }}>
          {`Slurm 예약 생성을 다시 시도하시겠습니까?\n티켓 ID: ${record.externalTicketId}\n제목: ${record.title}`}
        </Typography.Text>
      ),
      okText: '재시도',
      cancelText: '취소',
      onOk: async () => {
        if (!useDummy) {
          await runAction(record.id, 'retry', async () => {
            const result = await retrySlurmReservationRequest(record.id);
            if (result.success) {
              messageApi.success(result.message);
            } else {
              messageApi.error(result.slurmError || result.message);
            }
            await loadRequests();
          });
          return;
        }

        const retriedAt = new Date().toISOString();
        updateRequest(record.id, (request) => ({
          ...request,
          status: 'APPLYING_TO_SLURM',
          updatedAt: retriedAt,
          auditLogs: [
            ...request.auditLogs,
            createAuditLog('RETRY_SLURM', 'admin', '관리자가 Slurm 예약 생성을 다시 시도했습니다.', retriedAt),
          ],
        }));

        window.setTimeout(() => {
          const reservedAt = new Date().toISOString();
          updateRequest(record.id, (request) => ({
            ...request,
            status: 'SLURM_RESERVED',
            slurmReservationName: request.slurmReservationName || `insight-rsv-${request.id}`,
            slurmError: null,
            updatedAt: reservedAt,
            auditLogs: [
              ...request.auditLogs,
              createAuditLog('SLURM_RESERVED', 'Insight', 'Slurm 예약 생성이 완료되었습니다.', reservedAt),
            ],
          }));
        }, 650);
      },
    });
  };

  const columns: ColumnsType<ResourceReservationRequest> = [
    {
      title: '상태',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (value: ReservationRequestStatus) => renderStatusTag(value),
    },
    {
      title: '검증',
      dataIndex: 'validationStatus',
      key: 'validationStatus',
      width: 100,
      render: (value: ValidationStatus) => renderValidationTag(value),
    },
    {
      title: '티켓',
      dataIndex: 'externalTicketId',
      key: 'externalTicketId',
      width: 100,
    },
    {
      title: '신청 제목',
      dataIndex: 'title',
      key: 'title',
      width: 190,
    },
    {
      title: '신청자',
      dataIndex: 'requesterUsername',
      key: 'requesterUsername',
      width: 110,
    },
    {
      title: '파티션',
      dataIndex: 'partitionType',
      key: 'partitionType',
      width: 110,
      render: (value: PartitionType | null) => (value ? partitionLabels[value] : '-'),
    },
    {
      title: '시작 시간',
      dataIndex: 'startAt',
      key: 'startAt',
      width: 180,
      render: (value: string | null) => formatKstDateTime(value),
    },
    {
      title: '종료 시간',
      dataIndex: 'endAt',
      key: 'endAt',
      width: 180,
      render: (value: string | null) => formatKstDateTime(value),
    },
    {
      title: '사용 시간',
      dataIndex: 'durationText',
      key: 'durationText',
      width: 100,
    },
    {
      title: '요청 자원',
      key: 'resource',
      width: 140,
      render: (_, record) => formatRequestedResource(record),
    },
    {
      title: '접수 시간',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (value: string) => formatKstDateTime(value),
    },
    {
      title: '관리',
      key: 'actions',
      width: 230,
      fixed: 'right',
      render: (_, record) => (
        <Space size={6}>
          <Button
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              setSelectedRequestId(record.id);
            }}
          >
            상세
          </Button>
          {record.status === 'PENDING_APPROVAL' && record.validationStatus !== 'ERROR' ? (
            <Button
              size="small"
              type="primary"
              disabled={actionLoadingKey !== null}
              loading={actionLoadingKey === `approve:${record.id}`}
              onClick={(event) => {
                event.stopPropagation();
                approveRequest(record);
              }}
            >
              승인
            </Button>
          ) : null}
          {['PENDING_APPROVAL', 'VALIDATION_FAILED', 'SLURM_APPLY_FAILED'].includes(record.status) ? (
            <Button
              danger
              size="small"
              disabled={actionLoadingKey !== null}
              loading={actionLoadingKey === `reject:${record.id}`}
              onClick={(event) => {
                event.stopPropagation();
                rejectRequest(record);
              }}
            >
              거절
            </Button>
          ) : null}
          {record.status === 'SLURM_APPLY_FAILED' ? (
            <Button
              size="small"
              disabled={actionLoadingKey !== null}
              loading={actionLoadingKey === `retry:${record.id}`}
              onClick={(event) => {
                event.stopPropagation();
                retrySlurm(record);
              }}
            >
              재시도
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  return (
    <div className="resource-reservation-page">
      <div className="resource-reservation-toolbar">
        <Typography.Text type="secondary">
          외부 TSlurmDesk에서 접수된 예약 요청을 확인합니다.
        </Typography.Text>
        <Space wrap>
          <Typography.Text type="secondary">
            마지막 조회: {formatKstDateTime(lastFetchedAt, { seconds: true })}
          </Typography.Text>
          <Tag color={useDummy ? 'gold' : 'green'}>
            {useDummy ? '더미 데이터 사용 중' : 'Backend API 사용 중'}
          </Tag>
          <Button
            loading={loading}
            onClick={() => { void loadRequests(); }}
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
            <Typography.Text type="secondary">전체 요청</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.total}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">승인 대기</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.pending}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">검증 실패</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.validationFailed}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">Slurm 실패</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.slurmFailed}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">예약 완료</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.reserved}</span>
          </Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card className="resource-reservation-summary-card">
            <Typography.Text type="secondary">거절</Typography.Text>
            <span className="resource-reservation-summary-value">{summary.rejected}</span>
          </Card>
        </Col>
      </Row>

      <Card>
        <div className="resource-reservation-filters">
          <Select<RequestStatusFilter>
            className="resource-reservation-filter-select"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'OPEN', label: '처리 대기' },
              { value: 'ALL', label: '상태 전체' },
              { value: 'PENDING_APPROVAL', label: '승인 대기' },
              { value: 'VALIDATION_FAILED', label: '검증 실패' },
              { value: 'APPLYING_TO_SLURM', label: 'Slurm 반영 중' },
              { value: 'SLURM_RESERVED', label: '예약 완료' },
              { value: 'SLURM_APPLY_FAILED', label: 'Slurm 반영 실패' },
              { value: 'REJECTED', label: '거절' },
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
          <Select<ValidationFilter>
            className="resource-reservation-filter-select"
            value={validationFilter}
            onChange={setValidationFilter}
            options={[
              { value: 'ALL', label: '검증 전체' },
              { value: 'OK', label: '정상' },
              { value: 'WARNING', label: '경고' },
              { value: 'ERROR', label: '오류' },
            ]}
          />
          <Input
            className="resource-reservation-search"
            allowClear
            placeholder="티켓 ID, 제목, 신청자, 이메일, Slurm 예약명 검색"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
          />
          <Button onClick={resetFilters}>초기화</Button>
        </div>
      </Card>

      <div className="resource-reservation-table-wrap">
        <Table<ResourceReservationRequest>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={filteredRows}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 1800 }}
          locale={{ emptyText: <Empty description="조건에 맞는 예약 요청이 없습니다." /> }}
          onRow={(record) => ({
            onClick: () => setSelectedRequestId(record.id),
            style: { cursor: 'pointer' },
          })}
        />
      </div>

      <Drawer
        title="자원 예약 요청 상세"
        open={selectedRequest !== null}
        onClose={() => setSelectedRequestId(null)}
        width={780}
      >
        {selectedRequest ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Descriptions title="기본 정보" bordered size="small" column={1}>
              <Descriptions.Item label="요청 ID">{selectedRequest.id}</Descriptions.Item>
              <Descriptions.Item label="외부 티켓 ID">{selectedRequest.externalTicketId}</Descriptions.Item>
              <Descriptions.Item label="상태">{renderStatusTag(selectedRequest.status)}</Descriptions.Item>
              <Descriptions.Item label="검증 상태">{renderValidationTag(selectedRequest.validationStatus)}</Descriptions.Item>
              <Descriptions.Item label="신청 제목">{selectedRequest.title}</Descriptions.Item>
              <Descriptions.Item label="신청자">{selectedRequest.requesterUsername}</Descriptions.Item>
              <Descriptions.Item label="이메일">{selectedRequest.requesterEmail}</Descriptions.Item>
              <Descriptions.Item label="접수 시간">{formatKstDateTime(selectedRequest.createdAt)}</Descriptions.Item>
              <Descriptions.Item label="수정 시간">{formatKstDateTime(selectedRequest.updatedAt)}</Descriptions.Item>
            </Descriptions>

            <Descriptions title="요청 자원 정보" bordered size="small" column={1}>
              <Descriptions.Item label="파티션">
                {selectedRequest.partitionType ? partitionLabels[selectedRequest.partitionType] : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Slurm partition">{valueOrDash(selectedRequest.slurmPartition)}</Descriptions.Item>
              <Descriptions.Item label="CPU">{valueOrDash(selectedRequest.requestedCpuCores)}</Descriptions.Item>
              <Descriptions.Item label="Memory">
                {selectedRequest.requestedMemoryGb !== null ? `${selectedRequest.requestedMemoryGb}GB` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="GPU Node">{valueOrDash(selectedRequest.requestedGpuNodes)}</Descriptions.Item>
              <Descriptions.Item label="시작 시간">{formatKstDateTime(selectedRequest.startAt)}</Descriptions.Item>
              <Descriptions.Item label="종료 시간">{formatKstDateTime(selectedRequest.endAt)}</Descriptions.Item>
              <Descriptions.Item label="사용 시간">{selectedRequest.durationText}</Descriptions.Item>
            </Descriptions>

            <Descriptions title="검증 결과" bordered size="small" column={1}>
              <Descriptions.Item label="메시지">
                <ul className="resource-reservation-detail-list">
                  {selectedRequest.validationMessages.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </Descriptions.Item>
            </Descriptions>

            <Descriptions title="승인/거절 정보" bordered size="small" column={1}>
              <Descriptions.Item label="승인자">{valueOrDash(selectedRequest.approvedBy)}</Descriptions.Item>
              <Descriptions.Item label="승인 시간">{formatKstDateTime(selectedRequest.approvedAt)}</Descriptions.Item>
              <Descriptions.Item label="거절자">{valueOrDash(selectedRequest.rejectedBy)}</Descriptions.Item>
              <Descriptions.Item label="거절 시간">{formatKstDateTime(selectedRequest.rejectedAt)}</Descriptions.Item>
              <Descriptions.Item label="거절 사유">{valueOrDash(selectedRequest.rejectionReason)}</Descriptions.Item>
              <Descriptions.Item label="관리자 메모">{valueOrDash(selectedRequest.adminMemo)}</Descriptions.Item>
            </Descriptions>

            <Descriptions title="Slurm 생성 예정 정보" bordered size="small" column={1}>
              <Descriptions.Item label="slurmReservationName">
                {valueOrDash(selectedRequest.slurmReservationName)}
              </Descriptions.Item>
              <Descriptions.Item label="slurmPayloadPreview">
                <pre className="resource-reservation-json-preview">
                  {selectedRequest.slurmPayloadPreview
                    ? JSON.stringify(selectedRequest.slurmPayloadPreview, null, 2)
                    : '-'}
                </pre>
              </Descriptions.Item>
              <Descriptions.Item label="slurmError">{valueOrDash(selectedRequest.slurmError)}</Descriptions.Item>
            </Descriptions>

            <Descriptions title="처리 이력" bordered size="small" column={1}>
              <Descriptions.Item label="auditLogs">
                <div className="resource-reservation-audit-list">
                  {selectedRequest.auditLogs.map((log) => (
                    <div key={`${log.action}-${log.createdAt}`}>
                      <Typography.Text strong>{formatKstDateTime(log.createdAt)}</Typography.Text>
                      <Typography.Text>{` | ${log.action} | ${log.actor} | ${log.message}`}</Typography.Text>
                    </div>
                  ))}
                </div>
              </Descriptions.Item>
            </Descriptions>
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
