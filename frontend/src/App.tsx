import { Routes, Route, Navigate } from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';
import FeatureRoute from './components/FeatureRoute';
import Login from './pages/Login';
import Layout from './pages/Layout';
import Terminal from './pages/sub_pages/Terminal';
// EICN 납품: 가입자 승인 화면 비활성화.
// import Settings from './pages/sub_pages/Settings';
import ResourceReservationPage from './pages/sub_pages/settings/ResourceReservationPage';
// EICN 납품: 공개 가입신청 비활성화.
// import Register from './pages/Register';
import NotFoundInDashboard from './pages/error/NotFoundInDashboard';
import { monitoringPages } from './config/monitoring';
import { useProduct } from './config/product';

function ProductHome() {
    const { home_path } = useProduct();
    return <Navigate to={home_path} replace />;
}

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="/login" element={<Login />} />
            {/* EICN 납품: 공개 가입신청 직접 URL 비활성화.
            <Route path="/register" element={<Register />} /> */}
            <Route element={<PrivateRoute />}>
                <Route path="/ops" element={<Layout />}>
                    <Route index element={<ProductHome />} />
                    {monitoringPages.map(({ path, feature, component: Page }) => (
                        <Route key={path} path={path} element={<FeatureRoute feature={feature}><Page /></FeatureRoute>} />
                    ))}
                    <Route path="terminal">
                        <Route index element={<FeatureRoute feature="terminal"><Navigate to="master" replace /></FeatureRoute>} />
                        <Route path=":target" element={<FeatureRoute feature="terminal"><Terminal /></FeatureRoute>} />
                    </Route>
                    {/* EICN 납품: 가입자 승인 직접 URL 비활성화.
                    <Route path="settings" element={<Settings />} /> */}
                    <Route path="resource-reservations" element={<FeatureRoute feature="resource_reservations"><ResourceReservationPage /></FeatureRoute>} />
                    <Route path="*" element={<NotFoundInDashboard />} />
                </Route>
            </Route>
            <Route path="*" element={<NotFoundInDashboard />} />
        </Routes>
    );
}
