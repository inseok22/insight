import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Result, Button } from 'antd';
import XtermView from './TerminalView';          // xterm 실제 뷰(아래 참고)
import { TERMINALS } from '../../config/terminals';

export default function Terminal() {
  const { target } = useParams<{ target: string }>();

  const item = useMemo(
    () => TERMINALS.find(t => t.key === target),
    [target]
  );

  if (!item) {
    return (
      <Result
        status="404"
        title="대상을 찾을 수 없습니다"
        subTitle="올바르지 않은 터미널 대상이에요."
        extra={<Button type="primary" href="/terminal">목록으로</Button>}
      />
    );
  }

  return <XtermView wsUrl={item.ws}  />;
}