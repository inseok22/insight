import {
  DashboardOutlined, CloudServerOutlined, DeploymentUnitOutlined, DatabaseOutlined,
  InteractionOutlined, CloudOutlined, ApiOutlined, ThunderboltOutlined,
  FundOutlined, NodeIndexOutlined, SolutionOutlined,
} from '@ant-design/icons';
import Dashboard from '../pages/sub_pages/Dashboard';
import Node from '../pages/sub_pages/Node';
import Job from '../pages/sub_pages/Job';
import GPU from '../pages/sub_pages/GPU';
import Power from '../pages/sub_pages/Power';
import K8s from '../pages/sub_pages/k8s';
import Snmp from '../pages/sub_pages/Snmp';
import VLLM from '../pages/sub_pages/vLLM';
import VllmObservability from '../pages/sub_pages/VllmObservability';
import Trace from '../pages/sub_pages/Trace';
import UserTrace from '../pages/sub_pages/UserTrace';

export const monitoringPages = [
  { feature: 'vllm', path: 'vllm', label: 'Dashboard', group: 'llm', icon: ThunderboltOutlined, component: VLLM },
  { feature: 'vllm_observability', path: 'vllm-observability', label: 'Observability', group: 'llm', icon: FundOutlined, component: VllmObservability },
  { feature: 'trace', path: 'trace', label: 'Time Trace', group: 'llm', icon: NodeIndexOutlined, component: Trace },
  { feature: 'user_trace', path: 'user-trace', label: 'User Trace', group: 'llm', icon: SolutionOutlined, component: UserTrace },
  { feature: 'hpc_dashboard', path: 'dashboard', label: 'Dashboard', icon: DashboardOutlined, component: Dashboard },
  { feature: 'kubernetes', path: 'k8s', label: 'Kubernetes', icon: CloudOutlined, component: K8s },
  { feature: 'gpu', path: 'gpu', label: 'GPU', icon: DatabaseOutlined, component: GPU },
  { feature: 'server', path: 'server', label: 'Server', icon: CloudServerOutlined, component: Node },
  { feature: 'job', path: 'job', label: 'Job', icon: DeploymentUnitOutlined, component: Job },
  { feature: 'power', path: 'power', label: 'Power', icon: InteractionOutlined, component: Power },
  { feature: 'network', path: 'network', label: 'Network', icon: ApiOutlined, component: Snmp },
];
