import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Empty, Input, Space, Spin, Tag, Typography, theme } from 'antd';
import { MessageOutlined, PlusOutlined, SendOutlined, StopOutlined } from '@ant-design/icons';
import { ChatApiError, createChatSession, createRequestId, sendChatMessage, stopChatMessage } from '../../api/demoChatApi';

type Turn = {
  id: string;
  question: string;
  answer: string;
  traceId: string | null;
  status: 'waiting' | 'streaming' | 'completed' | 'cancelled' | 'error';
};
type ActiveRequest = {
  controller: AbortController;
  sessionId: string | null;
  requestId: string;
  cancelled: boolean;
};

export default function DemoChat() {
  const { token } = theme.useToken();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const active = useRef<ActiveRequest | null>(null);
  const sessionCreation = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      sessionCreation.current?.abort();
      const request = active.current;
      if (request) {
        request.cancelled = true;
        request.controller.abort();
        if (request.sessionId) void stopChatMessage(request.sessionId, request.requestId).catch(() => undefined);
      }
    };
  }, []);

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }); }, [turns]);

  const updateTurn = (id: string, update: (turn: Turn) => Turn) => {
    if (mounted.current) setTurns(current => current.map(turn => turn.id === id ? update(turn) : turn));
  };

  const startConversation = async () => {
    if (active.current || sessionCreation.current) return;
    const controller = new AbortController();
    sessionCreation.current = controller;
    setBusy(true);
    setError(null);
    try {
      const nextId = await createChatSession(controller.signal);
      if (!mounted.current) return;
      setSessionId(nextId);
      setTurns([]);
      setInput('');
      setExpired(false);
    } catch (failure) {
      if (mounted.current) setError(failure instanceof Error ? failure.message : '대화를 시작하지 못했습니다.');
    } finally {
      sessionCreation.current = null;
      if (mounted.current) setBusy(false);
    }
  };

  const submit = async () => {
    const message = input.trim();
    if (!message || active.current || sessionCreation.current || expired) return;
    const request: ActiveRequest = {
      controller: new AbortController(), sessionId, requestId: createRequestId(), cancelled: false,
    };
    active.current = request;
    setBusy(true);
    setStopping(false);
    setError(null);
    setInput('');
    setTurns(current => [...current, {
      id: request.requestId, question: message, answer: '', traceId: null, status: 'waiting',
    }]);
    try {
      if (!request.sessionId) {
        request.sessionId = await createChatSession(request.controller.signal);
        if (!mounted.current) return;
        if (request.cancelled) {
          updateTurn(request.requestId, turn => ({ ...turn, status: 'cancelled' }));
          return;
        }
        setSessionId(request.sessionId);
      }
      await sendChatMessage(request.sessionId, request.requestId, message, request.controller.signal, event => {
        if (!mounted.current) return;
        if (event.event === 'meta') {
          updateTurn(request.requestId, turn => ({ ...turn, traceId: event.data.trace_id }));
        } else if (event.event === 'delta') {
          updateTurn(request.requestId, turn => ({ ...turn, answer: turn.answer + event.data.text, status: 'streaming' }));
        } else if (event.event === 'error') {
          setError(event.data.message);
          updateTurn(request.requestId, turn => ({ ...turn, status: 'error' }));
        } else {
          updateTurn(request.requestId, turn => ({ ...turn, status: event.data.status }));
        }
      });
    } catch (failure) {
      if (!mounted.current) return;
      if (request.cancelled) {
        updateTurn(request.requestId, turn => ({ ...turn, status: 'cancelled' }));
      } else {
        updateTurn(request.requestId, turn => ({ ...turn, status: 'error' }));
        setError(failure instanceof Error ? failure.message : '채팅 서버와 연결하지 못했습니다.');
        if (failure instanceof ChatApiError && failure.status === 404) setExpired(true);
      }
    } finally {
      if (active.current === request) active.current = null;
      if (mounted.current) { setBusy(false); setStopping(false); }
    }
  };

  const stop = async () => {
    const request = active.current;
    if (!request || request.cancelled) return;
    request.cancelled = true;
    setStopping(true);
    try {
      if (request.sessionId) await stopChatMessage(request.sessionId, request.requestId);
    } catch {
      // Disconnect is also a cancellation signal to the backend.
    } finally {
      if (active.current === request) request.controller.abort();
    }
  };

  return <section aria-label="시연 채팅" style={{ height: 'calc(100dvh - 135px)', minHeight: 400,
    display: 'flex', flexDirection: 'column', gap: 12, padding: 8 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
      <div>
        <Typography.Title level={4} style={{ margin: 0 }}><MessageOutlined /> 시연 채팅</Typography.Title>
        <Typography.Text type="secondary">질문마다 생성되는 Trace와 모델 답변을 확인합니다.</Typography.Text>
      </div>
      <Button icon={<PlusOutlined />} onClick={() => void startConversation()} disabled={busy}>새 대화</Button>
    </div>
    <Typography.Text type="secondary" style={{ fontSize: 12, overflowWrap: 'anywhere' }}>
      {sessionId ? `Session · ${sessionId}` : '첫 질문을 보내면 새 대화가 시작됩니다.'}
      {' · '}대화 이력은 임시 보관되며 서버 재시작 시 사라집니다.
    </Typography.Text>
    {error && <Alert type="error" showIcon message={error} />}
    <div role="log" aria-label="대화 내용" aria-live="polite" aria-relevant="additions text"
      style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '8px 12px', borderRadius: 8,
        background: token.colorFillAlter }}>
      {!turns.length && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="모델에게 질문해 보세요." />}
      {turns.map(turn => <article key={turn.id} style={{ marginBottom: 24 }}>
        <div style={{ marginLeft: '12%', padding: '12px 16px', borderRadius: 8, background: token.colorPrimaryBg }}>
          <Typography.Text strong>나</Typography.Text>
          <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{turn.question}</div>
        </div>
        <div style={{ marginTop: 12, marginRight: '8%', padding: '12px 16px', borderRadius: 8,
          background: token.colorBgContainer }}>
          <Space style={{ marginBottom: 8 }}>
            <Typography.Text strong>모델</Typography.Text>
            {(turn.status === 'waiting' || turn.status === 'streaming') && <Spin size="small" />}
            {turn.status === 'cancelled' && <Tag>중단됨</Tag>}
            {turn.status === 'error' && <Tag color="error">응답 실패</Tag>}
          </Space>
          <div style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            {turn.answer || (turn.status === 'waiting' ? '응답을 기다리고 있습니다…'
              : turn.status === 'cancelled' ? '응답 생성을 중단했습니다.' : turn.status === 'error' ? '답변을 완료하지 못했습니다.' : '')}
          </div>
          {(turn.status === 'cancelled' || turn.status === 'error') && <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            완료되지 않은 질문과 답변은 후속 대화 문맥에 포함되지 않습니다.
          </Typography.Text>}
          {turn.traceId && <div style={{ marginTop: 8, fontSize: 11, color: token.colorTextSecondary,
            overflowWrap: 'anywhere' }}>Trace · {turn.traceId}</div>}
        </div>
      </article>)}
      <div ref={bottom} />
    </div>
    <form onSubmit={event => { event.preventDefault(); void submit(); }}>
      <Input.TextArea aria-label="질문 입력" placeholder="질문을 입력하세요. (Enter 전송 · Shift+Enter 줄바꿈)"
        value={input} onChange={event => setInput(event.target.value)} maxLength={16000}
        autoSize={{ minRows: 2, maxRows: 5 }} disabled={busy || expired}
        onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault(); void submit();
          }
        }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>답변은 실제 모델이 생성합니다.</Typography.Text>
        {busy && active.current ? <Button danger icon={<StopOutlined />} onClick={() => void stop()}
          loading={stopping} disabled={stopping}>{stopping ? '중단 중' : '생성 중지'}</Button>
          : <Button type="primary" htmlType="submit" icon={<SendOutlined />} loading={busy}
            disabled={busy || expired || !input.trim()}>전송</Button>}
      </div>
    </form>
  </section>;
}
