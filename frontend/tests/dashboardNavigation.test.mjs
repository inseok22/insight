import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/config/dashboardNavigation.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { dashboardGroups, dashboardSelection, dashboardMenuPath, hasServerMenu } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);
const template = readFileSync(new URL('../../docs/eicn-dashboard-urls.env.example', import.meta.url), 'utf8');
const targets = Object.fromEntries(template.split('\n').filter(line => /^[A-Z]+_URL=/.test(line)).map(line => {
  const [key, ...rest] = line.split('=');
  return [key.toLowerCase(), JSON.parse(rest.join('=').slice(1, -1))];
}));
const config = { dashboards: {}, dashboard_targets: targets };

test('14 template URLs map to the exact EICN server and model inventory', () => {
  const gpu = dashboardGroups(config, 'gpu_url');
  assert.deepEqual(gpu.map(group => [group.name, group.targets.length]), [
    ['ai-dev', 2], ['sLLM-SERVICE', 2], ['ta.eicn.co.kr', 3],
  ]);
  assert.deepEqual(dashboardGroups(config, 'node_url').map(group => group.name), [
    'ai-dev', 'DIRECT-PROJECT-1', 'sLLM-SERVICE', 'ta.eicn.co.kr',
  ]);
  assert.deepEqual(dashboardGroups(config, 'vllm_url')[0].targets.map(item => item.name), [
    'bmt-vllm-base', 'bmt-vllm-ft', 'eicn-rag-llm-gemma4',
  ]);
  let count = 0;
  for (const key of Object.keys(targets)) {
    for (const group of dashboardGroups(config, key)) {
      for (const item of group.targets) {
        assert.equal(item.url, targets[key].find(entry => entry.id === item.id).url);
        count++;
      }
    }
  }
  assert.equal(count, 14);
});

test('deep links restore the selected GPU/server and the added LLM tab', () => {
  const groups = dashboardGroups(config, 'gpu_url');
  const { group, selected } = dashboardSelection(groups, new URLSearchParams('server=ta-eicn&target=ta-eicn-gpu2'));
  assert.equal(selected.id, 'ta-eicn-gpu2');
  assert.equal(dashboardMenuPath('gpu', group), '/ops/gpu?server=ta-eicn');
  const llm = dashboardSelection(dashboardGroups(config, 'vllm_url'), new URLSearchParams('target=sllm-service-gemma4'));
  assert.equal(llm.selected.name, 'eicn-rag-llm-gemma4');
  assert.equal(llm.selected.url, targets.vllm_url[2].url);
});

test('unknown or cross-server target IDs fall back within the selected server', () => {
  const groups = dashboardGroups(config, 'gpu_url');
  const result = dashboardSelection(groups, new URLSearchParams('server=ai-dev&target=ta-eicn-gpu2'));
  assert.equal(result.selected.id, 'ai-dev-gpu0');
  assert.equal(dashboardSelection(groups, new URLSearchParams('server=missing&target=missing')).selected.id, 'ai-dev-gpu0');
});

test('unconfigured inventory keeps all menus but has no iframe URLs', () => {
  for (const key of Object.keys(targets)) {
    const groups = dashboardGroups({ dashboards: {} }, key);
    assert.ok(groups.length);
    assert.ok(groups.flatMap(group => group.targets).every(item => item.url === ''));
  }
});

test('legacy URLs and extra IDs do not create menus or tabs', () => {
  for (const key of Object.keys(targets)) {
    const expected = dashboardGroups(config, key);
    const legacy = dashboardGroups({ dashboards: { [key]: 'https://example.test/legacy' } }, key);
    assert.equal(legacy.length, expected.length);
    assert.ok(legacy.flatMap(group => group.targets).every(item => item.url === ''));
    const extra = dashboardGroups({ dashboards: {}, dashboard_targets: {
      [key]: [...targets[key], { id: 'default', name: '기존 대시보드', url: 'https://example.test/legacy' },
        { id: 'custom-server', name: 'Custom server', url: 'https://example.test/custom' }],
    } }, key);
    assert.deepEqual(extra, expected);
  }
});

test('offline delivery has exactly one server and eight GPU tabs, with configurable URLs', () => {
  const targets = Array.from({ length: 8 }, (_, i) => ({
    id: `gpu-${i}`, name: `GPU ${i}`, url: `http://10.0.0.1:8080/grafana/d/dcgm?var-gpu=${i}`,
  }));
  const offline = { dashboards: {}, dashboard_layout: 'single-server', dashboard_targets: {
    gpu_url: targets, vllm_url: [{ id: 'llm', name: 'LLM', url: 'http://10.0.0.1:8080/grafana/d/llm' }],
  } };
  const groups = dashboardGroups(offline, 'gpu_url');
  assert.equal(groups.length, 1);
  assert.equal(groups[0].targets.length, 8);
  assert.deepEqual(groups[0].targets, targets);
  assert.equal(dashboardSelection(groups, new URLSearchParams('target=gpu-7')).selected.id, 'gpu-7');
  assert.equal(dashboardGroups(offline, 'vllm_url')[0].targets.length, 1);
  assert.equal(dashboardGroups({ ...offline, dashboard_targets: {} }, 'gpu_url')[0].targets.length, 8);
});

test('KAC uses one GPU/Server URL and every registered LLM service without server menus', () => {
  const llms = Array.from({ length: 12 }, (_, n) => ({
    id: `llm-${n}`, name: `서비스 ${n}`, url: `https://example.test/llm-${n}`,
  }));
  const runtime = { dashboard_layout: 'services', dashboards: {
    gpu_url: 'https://example.test/d/gpu?var-server=All', node_url: 'https://example.test/d/server',
  }, dashboard_targets: { vllm_url: llms } };
  for (const key of ['gpu_url', 'node_url']) {
    const groups = dashboardGroups(runtime, key);
    assert.equal(groups.length, 1);
    assert.equal(groups[0].targets.length, 1);
    const selected = dashboardSelection(groups, new URLSearchParams('server=server-3&target=server-3-gpu-7')).selected;
    assert.equal(selected.url, runtime.dashboards[key]);
  }
  for (const path of ['vllm', 'gpu', 'server']) assert.equal(hasServerMenu(runtime, path), false);
  for (const path of ['gpu', 'server']) assert.equal(hasServerMenu(config, path), true);
  const groups = dashboardGroups(runtime, 'vllm_url');
  assert.deepEqual(groups[0].targets, llms);
  assert.equal(dashboardSelection(groups, new URLSearchParams('server=old&target=llm-11')).selected, llms[11]);
  assert.equal(dashboardSelection(groups, new URLSearchParams('target=deleted')).selected, llms[0]);
  llms[11].name = '변경한 이름';
  assert.equal(dashboardGroups(runtime, 'vllm_url')[0].targets[11].name, '변경한 이름');
});

test('empty KAC settings do not fall back to EICN inventory or invent services', () => {
  const empty = { dashboards: {}, dashboard_layout: 'services' };
  assert.deepEqual(dashboardGroups(empty, 'vllm_url')[0].targets, []);
  assert.equal(dashboardSelection(dashboardGroups(empty, 'vllm_url'), new URLSearchParams()).selected, undefined);
  for (const key of ['gpu_url', 'node_url']) {
    const targets = dashboardGroups(empty, key)[0].targets;
    assert.equal(targets.length, 1);
    assert.equal(targets[0].url, '');
  }
  assert.equal(dashboardMenuPath('vllm'), '/ops/vllm');
});
