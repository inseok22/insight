import type { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import ProductProvider from './ProductProvider';

type PrivateRouteProps = {
  children?: ReactNode;
};

export default function PrivateRoute({ children }: PrivateRouteProps) {
  const token = localStorage.getItem('token');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <ProductProvider authenticated>{children ?? <Outlet />}</ProductProvider>;
}
