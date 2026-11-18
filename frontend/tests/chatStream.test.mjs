import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/api/chatStream.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } });
const { readChatStream } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const encoder = new TextEncoder();
const event = (name, data, ending = '\n') => `event: ${name}${ending}data: ${JSON.stringify(data)}${ending}${ending}`;

function streamResponse(bytes, chunkSize = bytes.length) {
  return new Response(new ReadableStream({
    start(controller) {
      for (let index = 0; index < bytes.length; index += chunkSize) controller.enqueue(bytes.slice(index, index + chunkSize));
      controller.close();
    },
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } });
}

test('UTF-8 characters, CRLF and SSE boundaries survive one-byte network chunks', async () => {
  const events = [];
  const meta = { session_id: 'session-a', request_id: 'question-1', trace_id: 'trace-1' };
  const payload = ': heartbeat\r\n\r\n' + event('meta', meta, '\r\n')
    + event('delta', { text: '안녕하세요 ✈️\n두 번째 줄' }, '\r\n')
    + event('delta', { text: ' 이어지는 답변' }, '\r\n')
    + event('done', { status: 'completed' }, '\r\n');
  await readChatStream(streamResponse(encoder.encode(payload), 1), value => events.push(value));
  assert.deepEqual(events, [
    { event: 'meta', data: meta },
    { event: 'delta', data: { text: '안녕하세요 ✈️\n두 번째 줄' } },
    { event: 'delta', data: { text: ' 이어지는 답변' } },
    { event: 'done', data: { status: 'completed' } },
  ]);
});

test('model error and cancelled completion are delivered without inventing output', async () => {
  for (const status of ['error', 'cancelled']) {
    const events = [];
    const payload = event('error', { message: '모델 응답 실패', code: 'model_error' }) + event('done', { status });
    await readChatStream(streamResponse(encoder.encode(payload), 7), value => events.push(value));
    assert.deepEqual(events.at(-1), { event: 'done', data: { status } });
    assert.equal(events[0].data.message, '모델 응답 실패');
  }
});

test('multiline SSE data and unknown events preserve the following valid event', async () => {
  const events = [];
  const payload = 'event: future\ndata: non-JSON ignored\n\n'
    + 'event: delta\ndata: {\ndata: "text": "답변"}\n\n' + event('done', { status: 'completed' });
  await readChatStream(streamResponse(encoder.encode(payload), 5), value => events.push(value));
  assert.equal(events[0].data.text, '답변');
  assert.equal(events.length, 2);
});

test('truncated responses are errors instead of silently completed answers', async () => {
  for (const payload of [event('delta', { text: '부분 답변' }), 'event: done\ndata: {"status":"completed"}']) {
    await assert.rejects(readChatStream(streamResponse(encoder.encode(payload), 2), () => {}), /완료되지 않았습니다/);
  }
});

test('malformed JSON or event shape is rejected and stream reader is cancelled', async () => {
  for (const payload of ['event: delta\ndata: invalid\n\n', event('done', { status: 'unknown' }), event('delta', { text: 3 })]) {
    let cancelled = false;
    const response = new Response(new ReadableStream({
      start(controller) { controller.enqueue(encoder.encode(payload)); },
      cancel() { cancelled = true; },
    }), { headers: { 'Content-Type': 'text/event-stream' } });
    await assert.rejects(readChatStream(response, () => {}), /잘못된 채팅 응답/);
    assert.equal(cancelled, true);
    assert.equal(response.body.locked, false);
  }
});

test('done ends the stream without waiting for a still-open transport', async () => {
  let cancelled = false;
  const response = new Response(new ReadableStream({
    start(controller) { controller.enqueue(encoder.encode(event('done', { status: 'cancelled' }))); },
    cancel() { cancelled = true; },
  }), { headers: { 'Content-Type': 'text/event-stream' } });
  await readChatStream(response, () => {});
  assert.equal(cancelled, true);
  assert.equal(response.body.locked, false);
});

test('proxy HTML response and aborted transport are not accepted as a completed generation', async () => {
  await assert.rejects(readChatStream(new Response('<html>Gateway failure</html>'), () => {}), /스트리밍 응답/);
  const response = new Response(new ReadableStream({
    start(controller) { controller.error(new DOMException('Aborted', 'AbortError')); },
  }), { headers: { 'Content-Type': 'text/event-stream' } });
  await assert.rejects(readChatStream(response, () => {}), { name: 'AbortError' });
  assert.equal(response.body.locked, false);
});
