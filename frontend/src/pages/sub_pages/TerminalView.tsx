import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {Spin} from 'antd';
import {Terminal as XTerm} from 'xterm';
import {FitAddon} from 'xterm-addon-fit';
import {WebLinksAddon} from 'xterm-addon-web-links';
import 'xterm/css/xterm.css';

type Props = {
    wsUrl: string;
};

const FONT_SIZE = 14;
const LINE_HEIGHT = 1.2;
const BG = '#000';     // 검정 배경
const BOTTOM_GAP = 0;  // 필요 시 16~24로 여백 확보 가능

export default function TerminalView({wsUrl}: Props) {
    const outerRef = useRef<HTMLDivElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const termRef = useRef<XTerm | null>(null);
    const fitRef = useRef<FitAddon | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const [loading, setLoading] = useState(true);
    const [pixelHeight, setPixelHeight] = useState<number | null>(null);

    // 남은 뷰포트 높이를 측정해 px로 꽉 채우기
    const measure = () => {
        if (!outerRef.current) return;
        const top = outerRef.current.getBoundingClientRect().top;
        const h = Math.max(200, Math.floor(window.innerHeight - top - BOTTOM_GAP));
        setPixelHeight(h);
    };

    useLayoutEffect(() => {
        measure();
        const onResize = () => measure();
        window.addEventListener('resize', onResize);

        // 부모 컨테이너 크기 변화도 감지
        const target = outerRef.current?.parentElement || document.body;
        const ro = new ResizeObserver(() => measure());
        ro.observe(target);

        // 렌더 타이밍 보정
        const raf = requestAnimationFrame(measure);
        const t = setTimeout(measure, 0);

        return () => {
            window.removeEventListener('resize', onResize);
            ro.disconnect();
            cancelAnimationFrame(raf);
            clearTimeout(t);
        };
    }, []);

    // xterm 초기화 + WebSocket 연결
    useEffect(() => {
        if (!containerRef.current) return;

        const term = new XTerm({
            cursorBlink: true,
            fontFamily: 'ui-monospace, Menlo, Monaco, Consolas, monospace',
            fontSize: FONT_SIZE,
            lineHeight: LINE_HEIGHT,
            theme: {background: BG},
            scrollback: 4000,
        });
        const fit = new FitAddon();
        termRef.current = term;
        fitRef.current = fit;

        term.loadAddon(fit);
        term.loadAddon(new WebLinksAddon());
        term.open(containerRef.current);

        fit.fit();
        requestAnimationFrame(() => fit.fit());
        setTimeout(() => fit.fit(), 0);

        const token = localStorage.getItem('token');
        const url = token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            setLoading(false);
            ws.send(JSON.stringify({type: 'resize', cols: term.cols, rows: term.rows}));
        };
        ws.onmessage = (ev) => {
            if (typeof ev.data === 'string') term.write(ev.data);
            else term.write(new TextDecoder().decode(ev.data as ArrayBuffer));
        };
        ws.onclose = () => {
            term.writeln('\r\n\x1b[31m[연결 종료]\x1b[0m');
        };

        const disposeData = term.onData((data) => {
            ws.readyState === WebSocket.OPEN &&
            ws.send(JSON.stringify({type: 'data', data}));
        });

        const ro = new ResizeObserver(() => fit.fit());
        ro.observe(containerRef.current);

        return () => {
            try {
                disposeData.dispose();
            } catch {
            }
            try {
                ro.disconnect();
            } catch {
            }
            try {
                ws.close();
            } catch {
            }
            try {
                term.dispose();
            } catch {
            }
        };
    }, [wsUrl]);

    // 높이 변경 후 재맞춤
    useEffect(() => {
        if (pixelHeight && fitRef.current) {
            requestAnimationFrame(() => fitRef.current?.fit());
        }
    }, [pixelHeight]);

    return (
        <div
            ref={outerRef}
            style={{
                height: pixelHeight ? `${pixelHeight}px` : 'calc(100dvh - 80px)',
                display: 'flex',
                flexDirection: 'column',
            }}
        >
            {/* 상태바 제거: xterm만 꽉 차게 */}
            <div className="terminal-spin-wrap" style={{flex: 1, minHeight: 240, position: 'relative'}}>
                <Spin spinning={loading}>
                    <div
                        ref={containerRef}
                        style={{
                            width: '100%',
                            height: '88vh',
                            borderRadius: 6,
                            overflow: 'hidden',
                        }}
                    />
                </Spin>
            </div>
        </div>
    );
}