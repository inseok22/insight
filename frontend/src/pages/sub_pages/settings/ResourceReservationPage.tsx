import { Tabs, Typography } from 'antd';
import ResourceReservationApprovalTab from './ResourceReservationApprovalTab';
import ResourceReservationLookupTab from './ResourceReservationLookupTab';
import './ResourceReservationPage.css';

export default function ResourceReservationPage() {
  return (
    <div className="resource-reservation-page">
      <div className="resource-reservation-header">
        <div>
          <Typography.Title level={4} style={{ marginBottom: 4 }}>
            자원 예약 현황
          </Typography.Title>
          <Typography.Text type="secondary">
            Slurm 예약 조회와 외부 예약 요청 승인/거절을 관리합니다.
          </Typography.Text>
        </div>
      </div>

      <Tabs
        items={[
          {
            key: 'lookup',
            label: '자원 예약 조회',
            children: <ResourceReservationLookupTab />,
          },
          {
            key: 'approval',
            label: '자원 예약 승인/거절',
            children: <ResourceReservationApprovalTab />,
          },
        ]}
      />
    </div>
  );
}
