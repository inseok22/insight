import { useFrontendConfig } from '../../config/product';
// src/pages/sub_pages/UserTrace.tsx
import { useEffect, useState, useRef } from 'react';
import { Spin, Result, Button } from 'antd';



export default function UserTrace() {
    const EXTERNAL_URL = useFrontendConfig().dashboards["user_trace_url"] || undefined;
    const [loading, setLoading] = useState(true);
    const [loaded, setLoaded] = useState(false);
    const [shouldLoad, setShouldLoad] = useState(false);
    const iframeRef = useRef<HTMLIFrameElement>(null);

    // 컴포넌트 마운트 시 약간 지연 후 로드
    useEffect(() => {
        const timer = setTimeout(() => {
            setShouldLoad(true);
        }, 200);
        return () => clearTimeout(timer);
    }, []);

    // 로딩 타임아웃
    useEffect(() => {
        if (!shouldLoad) return;
        const t = setTimeout(() => {
            if (!loaded) setLoading(false);
        }, 2500);
        return () => clearTimeout(t);
    }, [loaded, shouldLoad]);

    // 컴포넌트 언마운트 시 iframe 리소스 정리
    useEffect(() => {
        return () => {
            if (iframeRef.current) {
                iframeRef.current.src = 'about:blank';
            }
        };
    }, []);

    if (!EXTERNAL_URL) return <Result status="warning" title="관제 화면 주소가 설정되지 않았습니다." />;

    const height = 'calc(100dvh - 64px - 1px - 32px)';

    return (
        <div style={{ height }}>
            {loading && (
                <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>
                    <Spin tip="불러오는 중..." />
                </div>
            )}

            {shouldLoad && (
                <iframe
                    ref={iframeRef}
                    src={EXTERNAL_URL}
                    title="UserTrace"
                    style={{
                        width: '100%',
                        height: '100%',
                        border: 0,
                        borderRadius: 6,
                        display: loading ? 'none' : 'block',
                    }}
                    loading="lazy"
                    referrerPolicy="no-referrer-when-downgrade"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    onLoad={() => {
                        setLoaded(true);
                        setLoading(false);
                    }}
                />
            )}

            {!loading && !loaded && (
                <Result
                    status="warning"
                    title="이 페이지는 임베드가 차단되어 있어요."
                    subTitle="보안 정책(X-Frame-Options 또는 Content-Security-Policy)으로 인해 임베드가 거부됐습니다."
                    extra={
                        <Button
                            type="primary"
                            onClick={() => window.open(EXTERNAL_URL, '_blank', 'noopener,noreferrer')}
                        >
                            새 탭에서 열기
                        </Button>
                    }
                />
            )}
        </div>
    );
}
