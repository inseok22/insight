import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';

// Render the production components without a DB, browser or external dashboards.
const require = createRequire(import.meta.url);
const { outputFiles } = await build({
  stdin: {
    contents: `
      import { renderToStaticMarkup } from 'react-dom/server';
      import { MemoryRouter } from 'react-router-dom';
      import { ProductContext, FrontendContext } from './src/config/product';
      import TargetDashboard from './src/components/TargetDashboard';
      import FeatureRoute from './src/components/FeatureRoute';
      import Layout from './src/pages/Layout';
      import { monitoringPages } from './src/config/monitoring';
      export { clearAuthStorage } from './src/utils/auth';
      export function render(config, key, route, feature = 'vllm') {
        return renderToStaticMarkup(
          <MemoryRouter initialEntries={[route]}>
            <ProductContext.Provider value={config}>
              <FrontendContext.Provider value={config}>
                <FeatureRoute feature={feature}>
                  <TargetDashboard dashboardKey={key} title="관제" />
                </FeatureRoute>
              </FrontendContext.Provider>
            </ProductContext.Provider>
          </MemoryRouter>
        );
      }
      export function renderRegistered(config, path, layout = false) {
        const { component: Page, feature } = monitoringPages.find(page => page.path === path);
        return renderToStaticMarkup(
          <MemoryRouter initialEntries={['/ops/' + path]}>
            <ProductContext.Provider value={config}>
              <FrontendContext.Provider value={config}>
                {layout ? <Layout /> : <FeatureRoute feature={feature}><Page /></FeatureRoute>}
              </FrontendContext.Provider>
            </ProductContext.Provider>
          </MemoryRouter>
        );
      }
    `,
    resolveDir: fileURLToPath(new URL('..', import.meta.url)),
    loader: 'tsx',
  },
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic',
  packages: 'external', loader: { '.css': 'empty' },
  define: { 'import.meta.env': '{}' },
});
const compiled = { exports: {} };
const storage = new Map();
new Function('require', 'module', 'exports', 'localStorage', outputFiles[0].text)(
  require, compiled, compiled.exports, {
    getItem: key => storage.get(key) ?? null,
    removeItem: key => storage.delete(key),
  },
);
const { render, renderRegistered, clearAuthStorage } = compiled.exports;

const config = {
  features: ['vllm', 'gpu', 'server', 'vllm_observability', 'trace', 'user_trace'], dashboard_layout: 'single-dashboard',
  dashboards: { gpu_url: 'https://example.test/gpu', node_url: 'https://example.test/server',
    vllm_url: 'https://example.test/llm', vllm_observability_url: 'https://example.test/observability',
    trace_url: 'https://example.test/time-trace', user_trace_url: 'https://example.test/user-trace' },
  dashboard_targets: { vllm_url: [
    { id: 'old', name: '기존 서비스', url: 'https://example.test/old' },
  ] },
};

test('LLM, GPU and Server render one iframe with no tabs or more menu, including old deep links', () => {
  for (const [key, feature] of [['vllm_url', 'vllm'], ['gpu_url', 'gpu'], ['node_url', 'server']]) {
    const html = render(config, key, `/ops/${feature}?server=server-3&target=old`, feature);
    assert.equal((html.match(/<iframe/g) ?? []).length, 1);
    assert.ok(html.includes(`src="${config.dashboards[key]}"`));
    assert.doesNotMatch(html, /role="tab"|더보기|기존 서비스/);
    const missing = render({ ...config, dashboards: {} }, key, `/ops/${feature}`, feature);
    assert.match(missing, /관제 화면 주소가 설정되지 않았습니다/);
    assert.doesNotMatch(missing, /<iframe|role="tab"|더보기/);
  }
});

test('existing EICN LLM tabs still load only the selected dashboard', () => {
  const eicn = { ...config, dashboard_layout: 'eicn', dashboard_targets: { vllm_url: [
    { id: 'bmt-vllm-base', name: 'bmt-vllm-base', url: 'https://example.test/base' },
    { id: 'bmt-vllm-ft', name: 'bmt-vllm-ft', url: 'https://example.test/ft' },
  ] } };
  const html = render(eicn, 'vllm_url', '/ops/vllm?target=bmt-vllm-ft');
  assert.equal((html.match(/<iframe/g) ?? []).length, 1);
  assert.match(html, /role="tab"/);
  assert.ok(html.includes('src="https://example.test/ft"'));
  assert.ok(!html.includes('src="https://example.test/base"'));
});

test('disabled direct routes cannot mount an iframe', () => {
  for (const feature of ['hpc_dashboard', 'job',
    'power', 'network', 'kubernetes', 'resource_reservations', 'terminal']) {
    const html = render(config, 'vllm_url', '/ops/vllm?server=three', feature);
    assert.match(html, /사용할 수 없는 기능입니다/);
    assert.doesNotMatch(html, /<iframe/);
  }
});

test('KAC restored LLM routes consume their own runtime URL and retain feature guards', () => {
  for (const [path, feature, key] of [
    ['vllm-observability', 'vllm_observability', 'vllm_observability_url'],
    ['trace', 'trace', 'trace_url'], ['user-trace', 'user_trace', 'user_trace_url'],
  ]) {
    const configured = { ...config, dashboards: { [key]: config.dashboards[key] } };
    assert.doesNotMatch(renderRegistered(configured, path), /사용할 수 없는 기능|관제 화면 주소가 설정되지/);
    assert.match(renderRegistered({ ...config, dashboards: {} }, path), /관제 화면 주소가 설정되지/);
    const disabled = renderRegistered({ ...configured, features: config.features.filter(item => item !== feature) }, path);
    assert.match(disabled, /사용할 수 없는 기능/);
    assert.doesNotMatch(disabled, /<iframe/);
  }
});

test('KAC sidebar restores Observability, Time Trace and User Trace after Dashboard', () => {
  const html = renderRegistered({ ...config, features: [...config.features, 'demo_chat'] }, 'vllm', true);
  assert.match(html, /Dashboard[\s\S]*Observability[\s\S]*Time Trace[\s\S]*User Trace/);
  assert.doesNotMatch(html, /시연 채팅/);
});

test('header uses the logged-in username and logout clears stale identity without touching preferences', () => {
  storage.set('user', JSON.stringify({ username: 'choi-login', full_name: 'Other Display Name' }));
  storage.set('userName', 'Old Admin');
  storage.set('token', 'test-token');
  storage.set('token_type', 'bearer');
  storage.set('theme', 'dark');
  const html = renderRegistered(config, 'vllm', true);
  assert.match(html, /choi-login/);
  assert.doesNotMatch(html, /Old Admin|Other Display Name|admin-users\/new|사용자 추가/);
  clearAuthStorage();
  assert.deepEqual([...storage.entries()], [['theme', 'dark']]);
  for (const invalid of ['{broken', 'null', JSON.stringify({ username: 123 })]) {
    storage.set('user', invalid);
    assert.doesNotThrow(() => renderRegistered(config, 'vllm', true));
    assert.doesNotMatch(renderRegistered(config, 'vllm', true), /choi-login|Old Admin/);
  }
  storage.clear();
});
