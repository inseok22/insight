import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Descriptions, Input, Modal, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { formatKstDateTime } from '../../../utils/time';

type ApprovalStatus = 'pending' | 'approved' | 'rejected';

type UserRow = {
  id: number;
  username: string;
  surname?: string | null;
  given_name?: string | null;
  full_name?: string | null;
  group_name?: string | null;
  email?: string | null;
  birth_date?: string | null;
  affiliation?: string | null;
  approval_status: ApprovalStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  rejection_reason?: string | null;
};

type ListParams = {
  approval_status?: ApprovalStatus;
  q?: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function renderStatusTag(status?: ApprovalStatus) {
  if (status === 'approved') return <Tag color="green">승인완료</Tag>;
  if (status === 'rejected') return <Tag color="red">거절</Tag>;
  return <Tag color="gold">대기</Tag>;
}

export default function UserApprovalPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [searchText, setSearchText] = useState('');
  const [listLoading, setListLoading] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rows, setRows] = useState<UserRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<UserRow | null>(null);

  const selectedRecord = useMemo(
    () => rows.find((row) => row.id === selectedId) ?? detail,
    [rows, selectedId, detail],
  );

  const loadList = useCallback(async (params: ListParams = { approval_status: 'pending' }) => {
    try {
      setListLoading(true);
      const qs = new URLSearchParams();
      if (params.approval_status) qs.set('approval_status', params.approval_status);
      if (params.q?.trim()) qs.set('q', params.q.trim());

      const response = await fetch(`${API_BASE_URL}/api/v1/users?${qs.toString()}`, {
        headers: {
          ...getAuthHeader(),
        },
      });
      const data = await response.json();
      if (!response.ok) {
        messageApi.error(data.detail || '신청 목록을 불러오지 못했습니다.');
        return;
      }
      setRows(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error(error);
      messageApi.error('신청 목록 조회 중 오류가 발생했습니다.');
    } finally {
      setListLoading(false);
    }
  }, [messageApi]);

  const loadDetail = useCallback(async (userId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/${userId}`, {
        headers: {
          ...getAuthHeader(),
        },
      });
      const data = await response.json();
      if (!response.ok) {
        messageApi.error(data.detail || '신청 상세를 불러오지 못했습니다.');
        return;
      }
      setDetail(data as UserRow);
      setSelectedId(userId);
    } catch (error) {
      console.error(error);
      messageApi.error('신청 상세 조회 중 오류가 발생했습니다.');
    }
  }, [messageApi]);

  useEffect(() => {
    void loadList({ approval_status: 'pending' });
  }, [loadList]);

  const onSearch = async () => {
    await loadList({ approval_status: 'pending', q: searchText });
  };

  const onRefresh = async () => {
    await loadList({ approval_status: 'pending', q: searchText });
  };

  const closeModal = () => {
    setSelectedId(null);
    setDetail(null);
  };

  const handleApproval = async (status: 'approved' | 'rejected') => {
    if (!selectedRecord) return;
    const setLoading = status === 'approved' ? setApproveLoading : setRejectLoading;

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/v1/users/${selectedRecord.id}/approval`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ status }),
      });
      const data = await response.json();

      if (!response.ok) {
        messageApi.error(data.detail || '처리 중 오류가 발생했습니다.');
        return;
      }

      if (status === 'approved') {
        setDetail((prev) => (
          prev && prev.id === selectedRecord.id
            ? {
                ...prev,
                approval_status: 'approved',
                is_active: false,
              }
            : prev
        ));
        messageApi.success('승인 완료되었습니다. 현재 화면은 대기 목록만 표시하므로 목록에서 제외됩니다.');
      } else {
        messageApi.success('거절되어 신청 레코드가 삭제되었습니다.');
      }

      await loadList({ approval_status: 'pending', q: searchText });
      closeModal();
    } catch (error) {
      console.error(error);
      messageApi.error('처리 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<UserRow> = [
    {
      title: '신청일시',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => formatKstDateTime(value),
    },
    {
      title: '이름',
      dataIndex: 'full_name',
      key: 'full_name',
      width: 140,
      render: (value?: string | null) => value || '-',
    },
    {
      title: '아이디',
      dataIndex: 'username',
      key: 'username',
      width: 140,
    },
    {
      title: '이메일',
      dataIndex: 'email',
      key: 'email',
      render: (value?: string | null) => value || '-',
    },
    {
      title: '상태',
      dataIndex: 'approval_status',
      key: 'approval_status',
      width: 130,
      render: (value: ApprovalStatus) => renderStatusTag(value),
    },
  ];

  return (
    <div>
      {contextHolder}
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }} align="start">
        <div>
          <Typography.Title level={4} style={{ marginBottom: 4 }}>
            Desk 가입신청 관리
          </Typography.Title>
          <Typography.Text type="secondary">
            기본 목록은 대기(pending) 신청만 조회합니다.
          </Typography.Text>
        </div>
        <Space>
          <Typography.Text type="secondary" style={{ whiteSpace: 'nowrap' }}>
            현재 화면은 대기 신청만 표시합니다.
          </Typography.Text>
          <Input.Search
            placeholder="이름 또는 아이디 검색"
            allowClear
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={() => { void onSearch(); }}
            style={{ width: 260 }}
          />
          <Button onClick={() => { void onRefresh(); }}>
            새로고침
          </Button>
        </Space>
      </Space>

      <Table<UserRow>
        rowKey="id"
        loading={listLoading}
        columns={columns}
        dataSource={rows}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        onRow={(record) => ({
          onClick: () => {
            void loadDetail(record.id);
          },
          style: { cursor: 'pointer' },
        })}
      />

      <Modal
        title="가입신청 상세"
        open={selectedId !== null}
        onCancel={closeModal}
        destroyOnClose
        width={720}
        footer={[
          <Button key="close" onClick={closeModal}>
            닫기
          </Button>,
          <Button
            key="reject"
            danger
            loading={rejectLoading}
            onClick={() => {
              void handleApproval('rejected');
            }}
          >
            거절
          </Button>,
          <Button
            key="approve"
            type="primary"
            loading={approveLoading}
            onClick={() => {
              void handleApproval('approved');
            }}
          >
            승인
          </Button>,
        ]}
      >
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          승인 전, 반드시 Desk/OpenLDAP 수동 등록 완료 여부를 확인하세요.
        </Typography.Paragraph>
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="신청일시">{formatKstDateTime(selectedRecord?.created_at)}</Descriptions.Item>
          <Descriptions.Item label="이름">{selectedRecord?.full_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="아이디">{selectedRecord?.username || '-'}</Descriptions.Item>
          <Descriptions.Item label="그룹">{selectedRecord?.group_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="이메일">{selectedRecord?.email || '-'}</Descriptions.Item>
          <Descriptions.Item label="생년월일">{selectedRecord?.birth_date || '-'}</Descriptions.Item>
          <Descriptions.Item label="소속">{selectedRecord?.affiliation || '-'}</Descriptions.Item>
          <Descriptions.Item label="상태">
            {renderStatusTag(selectedRecord?.approval_status)}
          </Descriptions.Item>
        </Descriptions>
      </Modal>
    </div>
  );
}
