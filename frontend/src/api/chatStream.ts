export type ChatStreamEvent =
  | { event: 'meta'; data: { session_id: string; request_id: string; trace_id: string | null } }
  | { event: 'delta'; data: { text: string } }
  | { event: 'error'; data: { message: string; code: string } }
  | { event: 'done'; data: { status: 'completed' | 'cancelled' | 'error' } };

function decodeEvent(event: string, data: string): ChatStreamEvent | null {
  if (!['meta', 'delta', 'error', 'done'].includes(event)) return null;
  const value: unknown = JSON.parse(data);
  if (!value || typeof value !== 'object') throw new Error('잘못된 채팅 응답입니다.');
  const body = value as Record<string, unknown>;
  if (event === 'meta' && typeof body.session_id === 'string' && typeof body.request_id === 'string'
      && (body.trace_id === null || typeof body.trace_id === 'string')) {
    return { event, data: { session_id: body.session_id, request_id: body.request_id, trace_id: body.trace_id } };
  }
  if (event === 'delta' && typeof body.text === 'string') return { event, data: { text: body.text } };
  if (event === 'error' && typeof body.message === 'string' && typeof body.code === 'string') {
    return { event, data: { message: body.message, code: body.code } };
  }
  if (event === 'done' && (body.status === 'completed' || body.status === 'cancelled' || body.status === 'error')) {
    return { event, data: { status: body.status } };
  }
  throw new Error('잘못된 채팅 응답입니다.');
}

// SSE lines and UTF-8 code points can both cross network chunk boundaries.
export async function readChatStream(response: Response, onEvent: (event: ChatStreamEvent) => void) {
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('스트리밍 응답을 받지 못했습니다.');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let event = '';
  let lines: string[] = [];
  let completed = false;

  const consumeLine = (line: string) => {
    if (!line) {
      if (lines.length) {
        let parsed: ChatStreamEvent | null;
        try { parsed = decodeEvent(event, lines.join('\n')); }
        catch { throw new Error('잘못된 채팅 응답입니다.'); }
        if (parsed) {
          onEvent(parsed);
          if (parsed.event === 'done') completed = true;
        }
      }
      event = '';
      lines = [];
      return;
    }
    if (line.startsWith(':')) return; // heartbeat
    const colon = line.indexOf(':');
    const field = colon < 0 ? line : line.slice(0, colon);
    const raw = colon < 0 ? '' : line.slice(colon + 1);
    const value = raw.startsWith(' ') ? raw.slice(1) : raw;
    if (field === 'event') event = value;
    if (field === 'data') lines.push(value);
  };

  try {
    while (!completed) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let match: RegExpExecArray | null;
      while ((match = /\r\n|\r|\n/.exec(buffer))) {
        // Wait for a possible LF after a CR at the end of the current chunk.
        if (!done && match[0] === '\r' && match.index === buffer.length - 1) break;
        const line = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        consumeLine(line);
        if (completed) break;
      }
      if (buffer.length > 1_048_576) throw new Error('채팅 응답 크기를 초과했습니다.');
      if (done) break;
    }
    if (!completed) throw new Error('응답 연결이 종료되었습니다. 답변이 완료되지 않았습니다.');
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
