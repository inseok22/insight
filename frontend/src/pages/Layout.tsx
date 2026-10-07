import {useCallback, useMemo, useState, useEffect} from 'react';
import {Layout, Menu, Breadcrumb, Button, theme, Avatar, Dropdown, Space, Typography, ConfigProvider, Badge, Empty, Popover, Spin} from 'antd';
import type {MenuProps} from 'antd';
import {
    UserOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
    DownOutlined, LogoutOutlined, IdcardOutlined, BellOutlined, CalendarOutlined, RobotOutlined,
} from '@ant-design/icons';
import { monitoringPages } from '../config/monitoring';
import { useProduct, useFrontendConfig } from '../config/product';
import { dashboardGroups, dashboardMenuPath, dashboardSelection, hasServerMenu } from '../config/dashboardNavigation';
import {Outlet, useLocation, useNavigate} from 'react-router-dom';
import {TERMINALS} from '../config/terminals';
import {formatKstDate, formatKstShortDate} from '../utils/time';

const {Header, Sider, Content} = Layout;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const NOTIFICATION_LIMIT = 5;
const NOTIFICATION_POLL_INTERVAL_MS = 30_000;

type PendingUserNotification = {
    id: number;
    username: string;
    full_name?: string | null;
    created_at: string;
};

function getAuthHeader(): Record<string, string> {
    const token = localStorage.getItem('token');
    return token ? {Authorization: `Bearer ${token}`} : {};
}

function getApplicantName(user: PendingUserNotification) {
    return user.full_name?.trim() || user.username;
}

export default function Admin() {
    const { features, product_name, short_name, home_path } = useProduct();
    // EICN 납품: 가입자 승인 및 알림 비활성화.
    const userApprovalEnabled = false;
    const frontendConfig = useFrontendConfig();
    const [collapsed, setCollapsed] = useState(false);
    const [openKeys, setOpenKeys] = useState<string[]>(['llm']); // LLM 그룹 기본 펼침
    const [notificationOpen, setNotificationOpen] = useState(false);
    const [notificationLoading, setNotificationLoading] = useState(false);
    const [pendingNotifications, setPendingNotifications] = useState<PendingUserNotification[]>([]);
    const {token} = theme.useToken();
    const navigate = useNavigate();
    const {pathname, search} = useLocation();

    const menuItems: MenuProps['items'] = useMemo(() => {
        const enabled = monitoringPages.filter(page => features.includes(page.feature));
        const item = (page: typeof monitoringPages[number]) => ({
            key: `/ops/${page.path}`, label: page.label, icon: <page.icon />,
            ...(hasServerMenu(frontendConfig, page.path) ? {
                children: dashboardGroups(frontendConfig, page.path === 'gpu' ? 'gpu_url' : page.path === 'server' ? 'node_url' : 'vllm_url')
                    .map(group => ({ key: dashboardMenuPath(page.path, group), label: group.name })),
            } : {}),
        });
        const llm = enabled.filter(page => page.group === 'llm');
        return [
            ...(llm.length ? [{ key: 'llm', label: 'LLM', icon: <RobotOutlined />, children: llm.map(item) }] : []),
            ...enabled.filter(page => page.group !== 'llm').map(item),
        ];
    }, [features, frontendConfig]);

    // 선택된 메뉴 키 계산 및 선택된 표시 처리
    const selectedKey = useMemo(() => {
        const parts = pathname.split('/').filter(Boolean);
        if (parts[0] !== 'ops') return home_path;
        if (parts[1] === 'dashboard') return '/ops/dashboard';
        if (hasServerMenu(frontendConfig, parts[1])) {
            const { group } = dashboardSelection(
                dashboardGroups(frontendConfig, parts[1] === 'gpu' ? 'gpu_url' : parts[1] === 'server' ? 'node_url' : 'vllm_url'),
                new URLSearchParams(search),
            );
            return dashboardMenuPath(parts[1], group);
        }
        if (parts[1] === 'job') return '/ops/job';
        if (parts[1] === 'power') return '/ops/power';
        if (parts[1] === 'terminal' && parts[2]) return `/ops/terminal/${parts[2]}`;
        if (parts[1] === 'k8s') return '/ops/k8s';  // 쿠버네티스 추가
        if (parts[1] === 'network') return '/ops/network'; // network(구 snmp)
        if (parts[1] === 'vllm') return '/ops/vllm'; // vLLM 추가
        if (parts[1] === 'vllm-observability') return '/ops/vllm-observability'; // 추가
        if (parts[1] === 'trace') return '/ops/trace'; // 추가
        if (parts[1] === 'user-trace') return '/ops/user-trace'; // 추가
        if (parts[1] === 'settings') return '/ops/settings';
        if (parts[1]) return `/ops/${parts[1]}`;
        return home_path;
    }, [pathname, search, home_path, frontendConfig]);

    // 터미널 경로일 때 서브메뉴 자동 열림 (LLM 그룹은 사용자가 접기 전까지 펼침 유지)
    useEffect(() => {
        if (collapsed) return; // 접힘 상태에서는 열림 상태 무의미
        const section = pathname.split('/')[2];
        const keys = [
            ...(hasServerMenu(frontendConfig, section) ? [`/ops/${section}`] : []),
            ...(section === 'terminal' ? ['terminal'] : []),
            ...(monitoringPages.some(page => page.path === section && page.group === 'llm') ? ['llm'] : []),
        ];
        if (keys.length) setOpenKeys(current => [...new Set([...current, ...keys])]);
    }, [pathname, collapsed, frontendConfig]);

    const loadPendingNotifications = useCallback(async (silent = false) => {
        if (!silent) setNotificationLoading(true);
        try {
            const qs = new URLSearchParams({approval_status: 'pending'});
            const response = await fetch(`${API_BASE_URL}/api/v1/users?${qs.toString()}`, {
                headers: {
                    ...getAuthHeader(),
                },
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();
            const nextItems = (Array.isArray(data) ? data : [])
                .filter((item): item is PendingUserNotification => (
                    item
                    && typeof item.id === 'number'
                    && typeof item.username === 'string'
                    && typeof item.created_at === 'string'
                ))
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                .slice(0, NOTIFICATION_LIMIT);

            setPendingNotifications(nextItems);
        } catch (error) {
            console.error(error);
        } finally {
            if (!silent) setNotificationLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!userApprovalEnabled) return;
        void loadPendingNotifications();

        const intervalId = window.setInterval(() => {
            void loadPendingNotifications(true);
        }, NOTIFICATION_POLL_INTERVAL_MS);

        return () => {
            window.clearInterval(intervalId);
        };
    }, [loadPendingNotifications, userApprovalEnabled]);

    const onMenuClick: MenuProps['onClick'] = (e) => {
        if (e.keyPath.includes('terminal')) {
            // 하위 항목은 바로 라우팅
            navigate(e.key);
            return;
        }
        navigate(e.key);
    };

    const onOpenChange: MenuProps['onOpenChange'] = (keys) => {
        // LLM 등 그룹 메뉴를 자유롭게 펼치고 접을 수 있게 antd에 그대로 위임
        setOpenKeys(keys as string[]);
    };

    // Breadcrumb
    const breadcrumbItems = useMemo(() => {
        const parts = pathname.split('/').filter(Boolean); // ['dashboard','terminal','alpha']
        const items: { title: string }[] = [];
        // if (parts[0]) items.push({title: '대시보드'});
        if (parts[1] && parts[1] == "dashboard") items.push({title: 'Dashboard'});
        if (parts[1] && parts[1] == "server") items.push({title: 'Server'});
        if (parts[1] && parts[1] == "job") items.push({title: 'Job'});
        if (parts[1] && parts[1] == "gpu") items.push({title: 'GPU'});
        if (parts[1] && parts[1] == "power") items.push({title: 'Power'});
        if (parts[1] && parts[1] == "k8s") items.push({title: 'Kubernetes'});  // 쿠버네티스 추가
        if (parts[1] && parts[1] == "network") items.push({title: 'Network'}); //network(구 snmp)
        if (parts[1] && parts[1] == "vllm") items.push({title: 'LLM'}, {title: 'Dashboard'}); // 구 vLLM
        if (parts[1] && parts[1] == "vllm-observability") items.push({title: 'LLM'}, {title: 'Observability'}); // 구 VllmObservability
        if (parts[1] && parts[1] == "trace") items.push({title: 'LLM'}, {title: 'Time Trace'}); // 구 Trace
        if (parts[1] && parts[1] == "user-trace") items.push({title: 'LLM'}, {title: 'User Trace'}); // 구 UserTrace
        if (parts[1] && parts[1] == "settings") items.push({title: '가입신청 관리'});
        if (parts[1] && parts[1] == "resource-reservations") items.push({title: '자원 예약 현황'});


        if (parts[1] === 'terminal') {
            items.push({title: '터미널'});
            if (parts[2]) {
                const t = TERMINALS.find((x) => x.key === parts[2]);
                items.push({title: t?.name ?? parts[2]});
            }
        }
        if (parts[1] === 'gpu' || parts[1] === 'server' || parts[1] === 'vllm') {
            const field = parts[1] === 'gpu' ? 'gpu_url' : parts[1] === 'server' ? 'node_url' : 'vllm_url';
            const { group, selected } = dashboardSelection(dashboardGroups(frontendConfig, field), new URLSearchParams(search));
            if (group && hasServerMenu(frontendConfig, parts[1])) items.push({ title: group.name });
            if (selected && (parts[1] === 'vllm' || (group?.targets.length ?? 0) > 1)) items.push({ title: selected.name });
        }
        return items;
    }, [pathname, search, frontendConfig]);

    const userName = localStorage.getItem('userName') || 'Admin';
    const hasPendingNotifications = pendingNotifications.length > 0;

    const userMenuItems: MenuProps['items'] = [
        {key: 'profile', icon: <IdcardOutlined/>, label: '내 정보', disabled: true},
        // EICN 납품: 가입자 승인 메뉴 비활성화.
        // {key: 'settings', icon: <SettingOutlined/>, label: '가입신청 관리'},
        ...(features.includes('resource_reservations') ? [{key: 'resource-reservations', icon: <CalendarOutlined/>, label: '자원 예약 현황'}] : []),
        {key: 'logout', icon: <LogoutOutlined/>, label: '로그아웃', danger: true},
    ];
    const onUserMenuClick: MenuProps['onClick'] = ({key}) => {
        if (key === 'settings') {
            navigate('/ops/settings');
            return;
        }
        if (key === 'resource-reservations') {
            navigate('/ops/resource-reservations');
            return;
        }
        if (key === 'logout') {
            localStorage.removeItem('token');
            navigate('/login', {replace: true});
        }
    };

    const handleNotificationClick = () => {
        setNotificationOpen(false);
        navigate('/ops/settings');
    };

    const notificationContent = (
        <div style={{width: 320}}>
            <div style={{paddingBottom: 8}}>
                <Typography.Text strong>가입신청 알림</Typography.Text>
            </div>

            {notificationLoading ? (
                <div style={{display: 'flex', justifyContent: 'center', padding: '28px 0'}}>
                    <Spin size="small"/>
                </div>
            ) : hasPendingNotifications ? (
                <div style={{maxHeight: 360, overflowY: 'auto'}}>
                    {pendingNotifications.map((item, index) => (
                        <button
                            key={item.id}
                            type="button"
                            onClick={handleNotificationClick}
                            style={{
                                width: '100%',
                                textAlign: 'left',
                                border: 'none',
                                background: 'transparent',
                                cursor: 'pointer',
                                padding: '12px 0',
                                borderTop: index === 0 ? 'none' : `1px solid ${token.colorBorderSecondary}`,
                            }}
                        >
                            <Typography.Text strong style={{display: 'block', marginBottom: 4}}>
                                {`가입신청 | ${formatKstShortDate(item.created_at)}`}
                            </Typography.Text>
                            <Typography.Text type="secondary" style={{display: 'block', lineHeight: 1.5}}>
                                {`${getApplicantName(item)}이 ${formatKstDate(item.created_at)}에 가입신청을 하였습니다.`}
                            </Typography.Text>
                        </button>
                    ))}
                </div>
            ) : (
                <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="새로운 가입신청이 없습니다."
                    styles={{image: {height: 48}}}
                />
            )}
        </div>
    );

    return (
        <Layout style={{minHeight: '100vh'}}>
            <Sider
                collapsible
                collapsed={collapsed}
                trigger={null}
                width={248}
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
                            padding: collapsed ? '0 8px' : '0 16px',
                            width: '100%',
                            fontWeight: 700,
                            fontSize: collapsed ? 16 : 19,
                            color: '#fff',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                        }}
                    >
                        {collapsed ? short_name : product_name}
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
                        <Space size={4}>
                            {userApprovalEnabled && <Popover
                                trigger="click"
                                placement="bottomRight"
                                content={notificationContent}
                                open={notificationOpen}
                                onOpenChange={setNotificationOpen}
                            >
                                <Badge dot={hasPendingNotifications} offset={[-2, 2]}>
                                    <Button
                                        type="text"
                                        aria-label="가입신청 알림 열기"
                                        style={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}
                                    >
                                        <BellOutlined style={{fontSize: 18, color: token.colorText}}/>
                                    </Button>
                                </Badge>
                            </Popover>}

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
                        </Space>
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
