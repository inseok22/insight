import type { DashboardGroup, DashboardTarget, FrontendConfig, TargetDashboardKey } from './product';

const target = (id: string, name: string): DashboardTarget => ({ id, name, url: '' });

// EICN Grafana inventory. IDs also identify entries in the backend URL configuration.
const inventory: Record<TargetDashboardKey, DashboardGroup[]> = {
  vllm_url: [{ id: 'dashboard', name: 'Dashboard', targets: [
    target('bmt-vllm-base', 'bmt-vllm-base'), target('bmt-vllm-ft', 'bmt-vllm-ft'),
    target('sllm-service-gemma4', 'eicn-rag-llm-gemma4'),
  ] }],
  gpu_url: [
    { id: 'ai-dev', name: 'ai-dev', targets: [target('ai-dev-gpu0', 'GPU 0'), target('ai-dev-gpu1', 'GPU 1')] },
    { id: 'sllm-service', name: 'sLLM-SERVICE', targets: [target('sllm-service-gpu0', 'GPU 0'), target('sllm-service-gpu1', 'GPU 1')] },
    { id: 'ta-eicn', name: 'ta.eicn.co.kr', targets: [target('ta-eicn-gpu0', 'GPU 0'), target('ta-eicn-gpu1', 'GPU 1'), target('ta-eicn-gpu2', 'GPU 2')] },
  ],
  node_url: [
    { id: 'ai-dev', name: 'ai-dev', targets: [target('ai-dev', 'ai-dev')] },
    { id: 'direct-project-1', name: 'DIRECT-PROJECT-1', targets: [target('direct-project-1', 'DIRECT-PROJECT-1')] },
    { id: 'sllm-service', name: 'sLLM-SERVICE', targets: [target('sllm-service', 'sLLM-SERVICE')] },
    { id: 'ta-eicn', name: 'ta.eicn.co.kr', targets: [target('ta-eicn', 'ta.eicn.co.kr')] },
  ],
};

export function dashboardGroups(config: FrontendConfig, key: TargetDashboardKey): DashboardGroup[] {
  const configured = config.dashboard_targets?.[key] ?? [];
  if (config.dashboard_layout === 'services') {
    if (key === 'vllm_url') return [{ id: 'dashboard', name: 'Dashboard', targets: configured }];
    // Grafana owns server/GPU selection; Insight opens one complete dashboard URL.
    const name = key === 'gpu_url' ? 'GPU' : 'Server';
    return [{ id: 'dashboard', name, targets: [{
      id: 'default', name, url: config.dashboards[key] ?? '',
    }] }];
  }
  if (config.dashboard_layout === 'single-server') {
    const targets = key === 'gpu_url'
      ? Array.from({ length: 8 }, (_, i) => target(`gpu-${i}`, `GPU ${i}`))
      : [target(key === 'vllm_url' ? 'llm' : 'server', key === 'vllm_url' ? 'LLM Dashboard' : 'GPU Server')];
    return [{ id: key === 'vllm_url' ? 'dashboard' : 'gpu-server',
      name: key === 'vllm_url' ? 'Dashboard' : 'GPU Server',
      targets: targets.map(item => ({ ...item, url: configured.find(entry => entry.id === item.id)?.url ?? '' })),
    }];
  }
  // EICN: show only the agreed server/model inventory; ignore legacy URLs and IDs.
  return inventory[key].map(group => ({
    ...group,
    targets: group.targets.map(item => ({ ...item, url: configured.find(entry => entry.id === item.id)?.url ?? '' })),
  }));
}

export function dashboardSelection(groups: DashboardGroup[], params: URLSearchParams): {
  group: DashboardGroup | undefined; selected: DashboardTarget | undefined;
} {
  const group = groups.find(item => item.id === params.get('server')) ?? groups[0];
  const selected = group?.targets.find(item => item.id === params.get('target')) ?? group?.targets[0];
  return { group, selected };
}

export function dashboardMenuPath(path: string, group?: DashboardGroup) {
  return `/ops/${path}${group ? `?${new URLSearchParams({ server: group.id })}` : ''}`;
}

export function hasServerMenu(config: FrontendConfig, path: string) {
  return config.dashboard_layout !== 'services' && (path === 'gpu' || path === 'server');
}
