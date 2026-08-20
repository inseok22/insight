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
import ResourceReservationPage from './pages/sub_pages/settings/ResourceReservationPage';
import K8s from './pages/sub_pages/k8s.tsx'; //쿠버네티 추가됨
import Snmp from './pages/sub_pages/Snmp.tsx'; //snmp 추가
import VLLM from './pages/sub_pages/vLLM.tsx'; //vLLM 추가
import VllmObservability from './pages/sub_pages/VllmObservability.tsx'; //vLLM Observability 추가
import Trace from './pages/sub_pages/Trace.tsx'; //Trace 추가
import UserTrace from './pages/sub_pages/UserTrace.tsx'; //UserTrace 추가
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
                    <Route index element={<Navigate to="vllm" replace/>}/>
                    <Route path="dashboard" element={<Dashboard/>}/>
                    <Route index element={<Navigate to="server" replace/>}/>
                    <Route path="server" element={<Node/>}/>
                    <Route index element={<Navigate to="job" replace/>}/>
                    <Route path="job" element={<Job/>}/>
                    <Route index element={<Navigate to="gpu" replace/>}/>
                    <Route path="gpu" element={<GPU/>}/>
                    <Route index element={<Navigate to="power" replace/>}/>
                    <Route path="power" element={<Power/>}/>
                    <Route path="k8s" element={<K8s/>}/>
                    <Route path="network" element={<Snmp/>}/>
                    <Route path="vllm" element={<VLLM/>}/>
                    <Route path="vllm-observability" element={<VllmObservability/>}/>
                    <Route path="trace" element={<Trace/>}/>
                    <Route path="user-trace" element={<UserTrace/>}/>


                    <Route path="terminal">
                        <Route index element={<Navigate to="master" replace/>}/>
                        <Route path=":target" element={<Terminal/>}/>
                    </Route>
                    <Route path="settings" element={<Settings/>}/>
                    <Route path="resource-reservations" element={<ResourceReservationPage/>}/>
                </Route>
            </Route>
            <Route path="*" element={<NotFoundInDashboard />} />
            <Route path="*" element={<Navigate to="/login" replace/>}/>
        </Routes>
    );
}
