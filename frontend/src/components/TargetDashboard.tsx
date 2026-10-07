import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { dashboardGroups, dashboardSelection } from '../config/dashboardNavigation';
import { Alert, Button, Result, Spin, Tabs } from 'antd';
import { EllipsisOutlined } from '@ant-design/icons';
import { useFrontendConfig } from '../config/product';
import type { DashboardTarget, TargetDashboardKey } from '../config/product';
import './TargetDashboard.css';

function DashboardFrame({ target }: { target: DashboardTarget }) {
  const [loaded, setLoaded] = useState(false);
  const [delayed, setDelayed] = useState(false);

  useEffect(() => {
    if (loaded) return;
    const timer = window.setTimeout(() => setDelayed(true), 10_000);
    return () => window.clearTimeout(timer);
  }, [loaded]);

  return <div className="target-dashboard-frame">
    {!loaded && delayed && <Alert
      type="warning"
      showIcon
      message="화면 로딩이 지연되고 있습니다."
      description="계속 기다리거나 새 탭에서 연결 상태를 확인해 주세요."
      action={<Button href={target.url} target="_blank" rel="noopener noreferrer">새 탭에서 열기</Button>}
    />}
    <div className="target-dashboard-viewport">
      {!loaded && !delayed && <div className="target-dashboard-loading" role="status" aria-label="불러오는 중">
        <Spin />
      </div>}
      <iframe
        src={target.url}
        title={target.name}
        referrerPolicy="no-referrer-when-downgrade"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        onLoad={() => setLoaded(true)}
      />
    </div>
  </div>;
}

export default function TargetDashboard({ dashboardKey, title }: {
  dashboardKey: TargetDashboardKey; title: string;
}) {
  const config = useFrontendConfig();
  const [params, setParams] = useSearchParams();
  const serviceLayout = config.dashboard_layout === 'services';
  const { group, selected } = dashboardSelection(dashboardGroups(config, dashboardKey), params);
  if (!group) return <Result status="info" title="등록된 서버가 없습니다." />;
  if (!selected) return <Result status="info"
    title={dashboardKey === 'vllm_url' ? '등록된 LLM 서비스가 없습니다.' : '등록된 관제 화면이 없습니다.'}
    subTitle={group.name} />;
  const targets = group.targets;
  const selectTarget = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('target', id);
    if (serviceLayout) next.delete('server');
    else next.set('server', group.id);
    setParams(next);
  };
  const content = (item: DashboardTarget) => item.url
    ? <DashboardFrame key={`${dashboardKey}:${item.id}:${item.url}`} target={item} />
    : <Result status="info" title="관제 화면 주소가 설정되지 않았습니다."
        subTitle={serviceLayout ? item.name : `${title} · ${group.name}${item.name !== group.name ? ` · ${item.name}` : ''}`} />;

  return <div className="target-dashboard">
    {targets.length > 1 || (serviceLayout && dashboardKey === 'vllm_url') ? <Tabs
      className="target-dashboard-tabs"
      activeKey={selected.id}
      onChange={selectTarget}
      destroyOnHidden
      animated={false}
      // Ant Design measures tab widths and reveals this menu only on overflow.
      more={{ icon: <span className="target-dashboard-more"><EllipsisOutlined /> 더보기</span>, trigger: 'click' }}
      locale={{ dropdownAriaLabel: '다른 LLM/관제 화면 선택' }}
      items={targets.map(target => ({
        key: target.id,
        label: target.name,
        // Only the selected URL gets an iframe, including during tab changes.
        children: target.id === selected.id
          ? content(target)
          : null,
      }))}
    /> : content(selected)}
  </div>;
}
