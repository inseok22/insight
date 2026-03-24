import { useEffect, useState } from 'react';
import { Spin, Result, Button } from 'antd';

// 환경변수로 관리하면 배포마다 URL 바꾸기 용이합니다.
// .env 파일에 설정값 사용.
const EXTERNAL_URL = import.meta.env.VITE_JOB_URL;

export default function Job() {
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);

  // onLoad가 안 불리는(임베드 차단) 경우를 대비해 타임아웃 처리
  useEffect(() => {
    const t = setTimeout(() => {
      if (!loaded) setLoading(false);
    }, 2500);
    return () => clearTimeout(t);
  }, [loaded]);

  // 헤더(64) + 헤더 하단 보더(1) + 콘텐츠 패딩(16*2) 반영
  const height = 'calc(100dvh - 64px - 1px - 32px)';

  return (
    <div style={{ height }}>
      {loading && (
        <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>
          <Spin tip="불러오는 중..." />
        </div>
      )}

      <iframe
        src={EXTERNAL_URL}
        title="Node"
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