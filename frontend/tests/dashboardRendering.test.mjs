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
    `,
    resolveDir: fileURLToPath(new URL('..', import.meta.url)),
    loader: 'tsx',
  },
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic',
  packages: 'external', loader: { '.css': 'empty' },
});
const compiled = { exports: {} };
new Function('require', 'module', 'exports', outputFiles[0].text)(require, compiled, compiled.exports);
const { render } = compiled.exports;

const config = {
  features: ['vllm', 'gpu', 'server'], dashboard_layout: 'services',
  dashboards: { gpu_url: 'https://example.test/gpu', node_url: 'https://example.test/server' },
  dashboard_targets: {
    vllm_url: Array.from({ length: 12 }, (_, i) => ({
      id: `llm-${i}`, name: `LLM ${i}`, url: `https://example.test/llm-${i}`,
    })),
  },
};

test('empty LLM inventory and missing URL render useful states without an iframe', () => {
  const empty = render({ ...config, dashboard_targets: {} }, 'vllm_url', '/ops/vllm');
  assert.match(empty, /등록된 LLM 서비스가 없습니다/);
  assert.doesNotMatch(empty, /<iframe/);
  const missing = render({ ...config, dashboard_targets: {
    vllm_url: [{ id: 'pending', name: '준비 중인 LLM', url: '' }],
  } }, 'vllm_url', '/ops/vllm?target=pending');
  assert.match(missing, /관제 화면 주소가 설정되지 않았습니다/);
  assert.match(missing, /준비 중인 LLM/);
  assert.match(missing, /role="tab"/);
  assert.doesNotMatch(missing, /<iframe/);
});

test('a direct link mounts only the selected service out of twelve and ignores an old server', () => {
  const html = render(config, 'vllm_url', '/ops/vllm?server=server-3&target=llm-11');
  assert.equal((html.match(/<iframe/g) ?? []).length, 1);
  assert.equal((html.match(/role="tab"/g) ?? []).length, 12);
  assert.match(html, /src="https:\/\/example.test\/llm-11"/);
  assert.doesNotMatch(html, /src="https:\/\/example.test\/llm-0"/);
});

test('GPU and Server each render one full URL without tabs or old server/GPU selectors', () => {
  for (const [key, feature] of [['gpu_url', 'gpu'], ['node_url', 'server']]) {
    const html = render(config, key, `/ops/${feature}?server=server-3&target=server-3-gpu-7`, feature);
    assert.equal((html.match(/<iframe/g) ?? []).length, 1);
    assert.ok(html.includes(`src="${config.dashboards[key]}"`));
    assert.doesNotMatch(html, /role="tab"/);
    const missing = render({ ...config, dashboards: {} }, key, `/ops/${feature}`, feature);
    assert.match(missing, /관제 화면 주소가 설정되지 않았습니다/);
    assert.doesNotMatch(missing, /<iframe/);
  }
});

test('disabled direct routes cannot mount an iframe', () => {
  for (const feature of ['trace', 'vllm_observability', 'user_trace', 'hpc_dashboard', 'job',
    'power', 'network', 'kubernetes', 'resource_reservations', 'terminal']) {
    const html = render(config, 'vllm_url', '/ops/vllm?server=three', feature);
    assert.match(html, /사용할 수 없는 기능입니다/);
    assert.doesNotMatch(html, /<iframe/);
  }
});
