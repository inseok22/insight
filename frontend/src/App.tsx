import {Routes, Route, Navigate} from 'react-router-dom';
import PrivateRoute from './components/PrivateRoute';
import Login from "./pages/Login.tsx";
import Layout from './pages/Layout.tsx';
import Dashboard from './pages/sub_pages/Dashboard.tsx';
import Node from './pages/sub_pages/Node.tsx';
import Job from './pages/sub_pages/Job.tsx';
import GPU from './pages/sub_pages/GPU.tsx';
import Power from './pages/sub_pages/Power.tsx';
import Terminal from "./pages/sub_pages/Terminal.tsx";
import Settings from './pages/sub_pages/Settings';
import K8s from './pages/sub_pages/k8s.tsx'; //쿠버네티 추가됨
import Snmp from './pages/sub_pages/Snmp.tsx'; //snmp 추가
import Register from "./pages/Register.tsx"; // Desk회원가입

import NotFoundInDashboard from "./pages/error/NotFoundInDashboard.tsx";

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<Navigate to="/login" replace/>}/>
            <Route path="/login" element={<Login/>}/>
            <Route path="/register" element={<Register />} />
            <Route element={<PrivateRoute/>}>
                <Route path="/ops" element={<Layout/>}>
                    <Route index element={<Navigate to="dashboard" replace/>}/>
                    <Route path="dashboard" element={<Dashboard/>}/>
                    <Route index element={<Navigate to="node" replace/>}/>
                    <Route path="node" element={<Node/>}/>
                    <Route index element={<Navigate to="job" replace/>}/>
                    <Route path="job" element={<Job/>}/>
                    <Route index element={<Navigate to="gpu" replace/>}/>
                    <Route path="gpu" element={<GPU/>}/>
                    <Route index element={<Navigate to="power" replace/>}/>
                    <Route path="power" element={<Power/>}/>
                    <Route path="k8s" element={<K8s/>}/>
                    <Route path="snmp" element={<Snmp/>}/>


                    <Route path="terminal">
                        <Route index element={<Navigate to="master" replace/>}/>
                        <Route path=":target" element={<Terminal/>}/>
                    </Route>
                    <Route path="settings" element={<Settings/>}/>
                </Route>
            </Route>
            <Route path="*" element={<NotFoundInDashboard />} />
            <Route path="*" element={<Navigate to="/login" replace/>}/>
        </Routes>
    );
}