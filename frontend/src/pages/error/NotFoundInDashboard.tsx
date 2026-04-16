import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';

export default function NotFoundInDashboard() {
  const navigate = useNavigate();
  return (
    <Result
      status="404"
      title="페이지를 찾을 수 없어요"
      subTitle="경로가 올바르지 않거나 이동된 것 같아요."
      extra={
        <>
          <Button type="primary" onClick={() => navigate('/ops/dashboard')}>개요로 이동</Button>
          <Button onClick={() => navigate('/ops/terminal')}>터미널 목록</Button>
        </>
      }
    />
  );
}