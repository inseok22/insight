import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useProduct } from '../../config/product';

export default function NotFoundInDashboard() {
  const navigate = useNavigate();
  const { home_path, features } = useProduct();
  return (
    <Result
      status="404"
      title="페이지를 찾을 수 없어요"
      subTitle="경로가 올바르지 않거나 이동된 것 같아요."
      extra={
        <>
          <Button type="primary" onClick={() => navigate(home_path)}>첫 화면으로 이동</Button>
          {features.includes('terminal') && <Button onClick={() => navigate('/ops/terminal')}>터미널 목록</Button>}
        </>
      }
    />
  );
}