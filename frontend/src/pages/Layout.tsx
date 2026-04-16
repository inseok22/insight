import {useMemo, useState, useEffect} from 'react';
import {Layout, Menu, Breadcrumb, Button, theme, Avatar, Dropdown, Space, Typography, ConfigProvider} from 'antd';
import type {MenuProps} from 'antd';
import {
    DashboardOutlined, CloudServerOutlined, DeploymentUnitOutlined, DatabaseOutlined, InteractionOutlined, UserOutlined, SettingOutlined,
    MenuFoldOutlined, MenuUnfoldOutlined, DownOutlined, LogoutOutlined, IdcardOutlined, CloudOutlined, ApiOutlined //clo는 쿠버네티스
} from '@ant-design/icons';
import {Outlet, useLocation, useNavigate} from 'react-router-dom';
import {TERMINALS} from '../config/terminals';

const {Header, Sider, Content} = Layout;

export default function Admin() {
    const [collapsed, setCollapsed] = useState(false);
    const [openKeys, setOpenKeys] = useState<string[]>([]);
    const {token} = theme.useToken();
    const navigate = useNavigate();
    const {pathname} = useLocation();

    // 메뉴 구성(터미널 하위는 동적으로)
    const menuItems: MenuProps['items'] = useMemo(() => {
        // const terminalChildren = TERMINALS.map((t) => ({
        //     key: `/dashboard/terminal/${t.key}`,
        //     icon: <CodeOutlined/>,
        //     label: t.name,
        // }));
        return [
            {key: '/ops/dashboard', icon: <DashboardOutlined/>, label: 'Dashboard'},
            {key: '/ops/node', icon: <CloudServerOutlined/>, label: 'Node'},
            {key: '/ops/job', icon: <DeploymentUnitOutlined />, label: 'Job'},
            {key: '/ops/gpu', icon: <DatabaseOutlined />, label: 'GPU'},
            {key: '/ops/power', icon: <InteractionOutlined />, label: 'Power'},
            {key: '/ops/k8s', icon: <CloudOutlined />, label: 'Kubernetes'}, //쿠버네티스 추가
            {key: '/ops/snmp', icon: <ApiOutlined />, label: 'SNMP'}, //snmp추가
            // {
            //     key: 'terminal', label: '터미널', icon: <CodeOutlined/>, children: terminalChildren,
            // },
            {key: '/ops/settings', icon: <SettingOutlined/>, label: '가입신청 관리'},
        ];
    }, []);

    // 선택된 메뉴 키 계산 및 선택된 표시 처리
    const selectedKey = useMemo(() => {
        const parts = pathname.split('/').filter(Boolean);
        if (parts[0] !== 'ops') return '/ops/dashboard';
        if (parts[1] === 'dashboard') return '/ops/dashboard';
        if (parts[1] === 'node') return '/ops/node';
        if (parts[1] === 'job') return '/ops/job';
        if (parts[1] === 'gpu') return '/ops/gpu';
        if (parts[1] === 'power') return '/ops/power';
        if (parts[1] === 'terminal' && parts[2]) return `/ops/terminal/${parts[2]}`;
        if (parts[1] === 'k8s') return '/ops/k8s';  // 쿠버네티스 추가
        if (parts[1] === 'snmp') return '/ops/snmp'; // snmp추가
        if (parts[1] === 'settings') return '/ops/settings';
        if (parts[1]) return `/ops/${parts[1]}`;
        return '/ops/dashboard';
    }, [pathname]);

    // 터미널 경로일 때 서브메뉴 자동 열림
    useEffect(() => {
        if (collapsed) return; // 접힘 상태에서는 열림 상태 무의미
        if (pathname.startsWith('/ops/terminal')) setOpenKeys(['terminal']);
        else setOpenKeys([]);
    }, [pathname, collapsed]);

    const onMenuClick: MenuProps['onClick'] = (e) => {
        if (e.keyPath.includes('terminal')) {
            // 하위 항목은 바로 라우팅
            navigate(e.key);
            return;
        }
        navigate(e.key);
    };

    const onOpenChange: MenuProps['onOpenChange'] = (keys) => {
        // 한 번에 하나의 루트만 열리게 제어
        const rootKeys = ['terminal'];
        const latest = keys.find((k) => !openKeys.includes(k));
        setOpenKeys(latest && rootKeys.includes(latest) ? [latest] : []);
    };

    // Breadcrumb
    const breadcrumbItems = useMemo(() => {
        const parts = pathname.split('/').filter(Boolean); // ['dashboard','terminal','alpha']
        const items: { title: string }[] = [];
        // if (parts[0]) items.push({title: '대시보드'});
        if (parts[1] && parts[1] == "dashboard") items.push({title: 'Dashboard'});
        if (parts[1] && parts[1] == "node") items.push({title: 'Node'});
        if (parts[1] && parts[1] == "job") items.push({title: 'Job'});
        if (parts[1] && parts[1] == "gpu") items.push({title: 'GPU'});
        if (parts[1] && parts[1] == "power") items.push({title: 'Power'});
        if (parts[1] && parts[1] == "k8s") items.push({title: 'Kubernetes'});  // 쿠버네티스 추가
        if (parts[1] && parts[1] == "snmp") items.push({title: 'SNMP'}); //snmp 추가
        if (parts[1] && parts[1] == "settings") items.push({title: '가입신청 관리'});


        if (parts[1] === 'terminal') {
            items.push({title: '터미널'});
            if (parts[2]) {
                const t = TERMINALS.find((x) => x.key === parts[2]);
                items.push({title: t?.name ?? parts[2]});
            }
        }
        return items;
    }, [pathname]);

    const userName = localStorage.getItem('userName') || 'Admin';

    const userMenuItems: MenuProps['items'] = [
        {key: 'profile', icon: <IdcardOutlined/>, label: '내 정보', disabled: true},
        {type: 'divider'},
        {key: 'logout', icon: <LogoutOutlined/>, label: '로그아웃', danger: true},
    ];
    const onUserMenuClick: MenuProps['onClick'] = ({key}) => {
        if (key === 'logout') {
            localStorage.removeItem('token');
            navigate('/login', {replace: true});
        }
    };

    return (
        <Layout style={{minHeight: '100vh'}}>
            <Sider
                collapsible
                collapsed={collapsed}
                trigger={null}
                width={220}
                className="app-sider-dark"
                style={{
                    background: '#121923',   // 슬라이더 배경
                    borderRight: 'none',
                }}
            >
                <ConfigProvider
                    theme={{
                        components: {
                            Menu: {
                                itemColor: 'rgba(255,255,255,0.85)', // 기본 글자
                                itemHoverColor: '#fff',              // 호버 글자
                                itemHoverBg: 'rgba(255,255,255,0.08)',
                                itemSelectedColor: '#fff',           // 선택 글자
                                itemSelectedBg: 'rgba(255,255,255,0.16)',
                                groupTitleColor: 'rgba(255,255,255,0.55)',
                            },
                        },
                    }}
                >
                    {/* 브랜드 영역 */}
                    <div
                        className="sider-brand"
                        style={{
                            height: 56,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: collapsed ? 'center' : 'flex-start',
                            padding: collapsed ? '0 22px' : '0 26px',
                            width: '100%',
                            fontWeight: 700,
                            fontSize: 20,
                            color: '#fff',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                        }}
                    >
                        {collapsed ? 'TSlurm' : 'TSlurmOps'}
                    </div>

                    {/* 메뉴 */}
                    <Menu
                        mode="inline"
                        items={menuItems}
                        selectedKeys={[selectedKey]}
                        openKeys={openKeys}
                        onOpenChange={onOpenChange}
                        onClick={onMenuClick}
                        style={{background: 'transparent'}} // Menu 배경은 투명 → Sider 배경 사용
                    />
                </ConfigProvider>
            </Sider>

            <Layout>
                <Header
                    style={{
                        background: token.colorBgContainer,
                        borderBottom: `1px solid ${token.colorBorderSecondary}`,
                        paddingInline: 16,
                        display: 'flex', alignItems: 'center', gap: 12,
                    }}
                >
                    <Button
                        type="text"
                        aria-label={collapsed ? '메뉴 펼치기' : '메뉴 접기'}
                        icon={collapsed ? <MenuUnfoldOutlined/> : <MenuFoldOutlined/>}
                        onClick={() => setCollapsed((c) => !c)}
                    />
                    <Breadcrumb items={breadcrumbItems}/>

                    <div style={{marginLeft: 'auto'}}>
                        <Dropdown trigger={['click']} placement="bottomRight"
                                  menu={{items: userMenuItems, onClick: onUserMenuClick}}>
                            <Button type="text" aria-label="사용자 메뉴 열기"
                                    style={{display: 'flex', alignItems: 'center', paddingInline: 8}}>
                                <Space size={8}>
                                    <Avatar size={28} icon={<UserOutlined/>}/>
                                    <Typography.Text style={{color: token.colorText}}>{userName}</Typography.Text>
                                    <DownOutlined style={{fontSize: 12, color: token.colorTextSecondary}}/>
                                </Space>
                            </Button>
                        </Dropdown>
                    </div>
                </Header>

                <Content className="dashboard-content" style={{background: token.colorBgLayout}}>
                    <div
                        className="dashboard-inner"
                        style={{
                            background: token.colorBgContainer,
                            border: `1px solid ${token.colorBorderSecondary}`,
                        }}
                    >
                        <Outlet/>
                    </div>
                </Content>
            </Layout>
        </Layout>
    );
}
