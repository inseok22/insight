import { readChatStream } from './chatStream';
import type { ChatStreamEvent } from './chatStream';

// Browser requests always pass through the existing same-origin Nginx /api/ proxy.
const CHAT_API = '/api/v1/chat';

export class ChatApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function headers(): Record<string, string> {
  const token = localStorage.getItem('token');
  return { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function checkResponse(response: Response) {
  if (response.ok) return;
  const value: unknown = await response.json().catch(() => null);
  const detail = value && typeof value === 'object' && 'detail' in value ? value.detail : null;
  const message = response.status === 401 ? '로그인이 만료되었습니다. 다시 로그인해 주세요.'
    : response.status === 404 ? '대화를 찾을 수 없거나 채팅이 비활성화되었습니다. 새 대화를 시작해 주세요.'
    : typeof detail === 'string' ? detail : '채팅 요청을 처리하지 못했습니다.';
  throw new ChatApiError(message, response.status);
}

export async function createChatSession(signal: AbortSignal): Promise<string> {
  const response = await fetch(`${CHAT_API}/sessions`, { method: 'POST', headers: headers(), signal });
  await checkResponse(response);
  const value = await response.json();
  if (typeof value.session_id !== 'string') throw new Error('대화를 시작하지 못했습니다.');
  return value.session_id;
}

export async function sendChatMessage(sessionId: string, requestId: string, message: string,
  signal: AbortSignal, onEvent: (event: ChatStreamEvent) => void) {
  const response = await fetch(`${CHAT_API}/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST', headers: headers(), signal, body: JSON.stringify({ message, request_id: requestId }),
  });
  await checkResponse(response);
  await readChatStream(response, onEvent);
}

export async function stopChatMessage(sessionId: string, requestId: string) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(`${CHAT_API}/sessions/${encodeURIComponent(sessionId)}/stop`, {
      method: 'POST', headers: headers(), signal: controller.signal, keepalive: true,
      body: JSON.stringify({ request_id: requestId }),
    });
    await checkResponse(response);
  } finally {
    clearTimeout(timer);
  }
}

export function createRequestId(): string {
  // randomUUID is restricted to secure contexts; the demo also runs over HTTP on a LAN IP.
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
