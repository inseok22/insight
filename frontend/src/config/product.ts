import { createContext, useContext } from 'react';

export type ProductConfig = {
  profile: 'hpc' | 'llm';
  product_name: string;
  short_name: string;
  home_path: string;
  features: string[];
};
export type FrontendConfig = ProductConfig & {
  dashboards: Record<string, string | null>;
  terminals: { key: string; name: string; ws_path: string }[];
};
export const ProductContext = createContext<ProductConfig | null>(null);
export const FrontendContext = createContext<FrontendConfig | null>(null);
export function useProduct() {
  const config = useContext(ProductContext);
  if (!config) throw new Error('Product configuration is not loaded');
  return config;
}
export function useFrontendConfig() {
  const config = useContext(FrontendContext);
  if (!config) throw new Error('Frontend configuration is not loaded');
  return config;
}
