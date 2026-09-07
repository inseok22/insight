import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Button, Result, Spin } from 'antd';
import { Navigate } from 'react-router-dom';
import { FrontendContext, ProductContext } from '../config/product';
import type { FrontendConfig, ProductConfig } from '../config/product';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function ProductProvider({ children, authenticated = false }: {
  children: ReactNode; authenticated?: boolean;
}) {
  const [config, setConfig] = useState<ProductConfig | FrontendConfig | null>(null);
  const [error, setError] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const headers: Record<string, string> = authenticated
      ? { Authorization: `Bearer ${localStorage.getItem('token') || ''}` } : {};
    fetch(`${API_BASE_URL}/api/v1/config/${authenticated ? 'frontend' : 'product'}`, {
      headers, signal: controller.signal,
    }).then(async response => {
      if (authenticated && (response.status === 401 || response.status === 403)) {
        localStorage.removeItem('token');
        setUnauthorized(true);
        return;
      }
      if (!response.ok) throw new Error('Configuration request failed');
      const value = await response.json();
      if (!['hpc', 'llm'].includes(value.profile) || !Array.isArray(value.features)
        || typeof value.product_name !== 'string' || typeof value.short_name !== 'string'
        || !['/ops/vllm', '/ops/k8s'].includes(value.home_path)
        || (authenticated && (!value.dashboards || !Array.isArray(value.terminals)))) {
        throw new Error('Invalid product configuration');
      }
      if (!controller.signal.aborted) {
        document.title = value.product_name;
        setConfig(value);
      }
    }).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => controller.abort();
  }, [authenticated, attempt]);

  if (unauthorized) return <Navigate to="/login" replace />;
  if (error) return <Result status="error" title="제품 설정을 불러오지 못했습니다."
    subTitle="서버 연결을 확인한 후 다시 시도해 주세요."
    extra={<Button onClick={() => { setError(false); setAttempt(n => n + 1); }}>다시 시도</Button>} />;
  if (!config) return <div style={{ padding: 64, textAlign: 'center' }}><Spin /></div>;
  return <ProductContext.Provider value={config}>
    {authenticated
      ? <FrontendContext.Provider value={config as FrontendConfig}>{children}</FrontendContext.Provider>
      : children}
  </ProductContext.Provider>;
}
