export type TerminalTarget = {
  key: string;      // 라우트 파라미터로 쓸 식별자
  name: string;     // 메뉴/Breadcrumb에 보일 이름
  ws: string;       // 해당 서버의 WebSocket 주소
};

export const TERMINALS: TerminalTarget[] = [
  { key: 'master', name: 'Master', ws: 'ws://192.168.1.100:3001/term' },
  { key: 'node-a',  name: 'Node A',  ws: 'ws://192.168.1.100:3001/term' },
  { key: 'node-b', name: 'Node B', ws: 'ws://192.168.1.100:3001/term' },
];

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL;