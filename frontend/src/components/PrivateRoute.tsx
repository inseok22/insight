import type { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';

type PrivateRouteProps = {
  children?: ReactNode;
};

export default function PrivateRoute({ children }: PrivateRouteProps) {
  const token = localStorage.getItem('token');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
