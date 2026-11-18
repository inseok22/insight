import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';

const require = createRequire(import.meta.url);
const { outputFiles } = await build({
  stdin: {
    contents: `
      export * from './src/api/demoChatApi';
      import { renderToStaticMarkup } from 'react-dom/server';
      import { ProductContext } from './src/config/product';
      import FeatureRoute from './src/components/FeatureRoute';
      import { monitoringPages } from './src/config/monitoring';
      export function renderChat(features) {
        const page = monitoringPages.find(page => page.path === 'chat');
        const Page = page.component;
        return renderToStaticMarkup(
          <ProductContext.Provider value={{features}}>
            <FeatureRoute feature={page.feature}><Page /></FeatureRoute>
          </ProductContext.Provider>
        );
      }
    `,
    resolveDir: fileURLToPath(new URL('..', import.meta.url)), loader: 'tsx',
  },
  bundle: true, write: false, platform: 'node', format: 'cjs', jsx: 'automatic',
  packages: 'external', loader: { '.css': 'empty' },
});

function client(fetch, crypto = webcrypto) {
  const compiled = { exports: {} };
  new Function('require', 'module', 'exports', 'fetch', 'crypto', 'localStorage', outputFiles[0].text)(
    require, compiled, compiled.exports, fetch, crypto, { getItem: key => key === 'token' ? 'mock-login-token' : null },
  );
  return compiled.exports;
}

test('chat route uses the shared feature guard and renders only when enabled', () => {
  const api = client(() => { throw new Error('Rendering must not make requests'); });
  assert.match(api.renderChat([]), /사용할 수 없는 기능입니다/);
  assert.doesNotMatch(api.renderChat([]), /질문 입력|생성 중지/);
  const enabled = api.renderChat(['demo_chat']);
  assert.match(enabled, /질문 입력/);
  assert.match(enabled, /새 대화/);
  assert.doesNotMatch(enabled, /<iframe/);
});

test('session, message and stop requests use the existing auth and same-origin API without client user IDs', async () => {
  const calls = [];
  const api = client(async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/sessions')) return Response.json({ session_id: 'server-session-id' });
    if (url.endsWith('/stop')) return Response.json({ status: 'cancelling' });
    return new Response('event: done\ndata: {"status":"completed"}\n\n', {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  });
  const controller = new AbortController();
  const id = await api.createChatSession(controller.signal);
  await api.sendChatMessage(id, 'request-one', '첫 질문', controller.signal, () => {});
  await api.sendChatMessage(id, 'request-two', '후속 질문', controller.signal, () => {});
  await api.stopChatMessage(id, 'request-two');
  assert.deepEqual(calls.map(call => call.url), [
    '/api/v1/chat/sessions', '/api/v1/chat/sessions/server-session-id/messages',
    '/api/v1/chat/sessions/server-session-id/messages', '/api/v1/chat/sessions/server-session-id/stop',
  ]);
  for (const call of calls) {
    assert.equal(call.options.headers.Authorization, 'Bearer mock-login-token');
    assert.doesNotMatch(call.options.body ?? '', /user_id|api_key|secret_key/);
  }
  assert.deepEqual(JSON.parse(calls[1].options.body), { message: '첫 질문', request_id: 'request-one' });
  assert.equal(calls[1].options.signal, controller.signal);
  assert.equal(calls[3].options.keepalive, true);
});

test('expired or inaccessible session returns an explicit error without replaying the question', async () => {
  let count = 0;
  const api = client(async () => { count++; return Response.json({ detail: 'Not found' }, { status: 404 }); });
  await assert.rejects(api.sendChatMessage('old', 'request', '질문', new AbortController().signal, () => {}), error => {
    assert.equal(error.status, 404);
    assert.match(error.message, /새 대화를 시작/);
    return true;
  });
  assert.equal(count, 1);
});

test('LAN HTTP without randomUUID still creates distinct valid UUIDs', () => {
  const api = client(() => {}, { getRandomValues: array => webcrypto.getRandomValues(array) });
  const ids = Array.from({ length: 100 }, () => api.createRequestId());
  assert.equal(new Set(ids).size, 100);
  for (const id of ids) assert.match(id, /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/);
});
