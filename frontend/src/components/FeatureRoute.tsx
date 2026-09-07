import type { ReactNode } from 'react';
import { Result } from 'antd';
import { useProduct } from '../config/product';

export default function FeatureRoute({ feature, children }: { feature: string; children: ReactNode }) {
  const { features } = useProduct();
  return features.includes(feature) ? children : <Result status="403"
    title="사용할 수 없는 기능입니다." subTitle="현재 제품 구성에 포함되지 않은 기능입니다." />;
}
