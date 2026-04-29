import { useState } from 'react';
import { Button, Form, Input, Select, Typography, message } from 'antd';
import { UserOutlined, LockOutlined, TeamOutlined, MailOutlined } from '@ant-design/icons';
import { useSearchParams } from 'react-router-dom';

type RegisterFields = {
    username: string;
    password: string;
    confirmPassword: string;
    full_name: string;
    birth_year: string;
    birth_month: string;
    birth_day: string;
    affiliation: string;
    email: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const months = Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1).padStart(2, '0'),
    label: `${i + 1}월`,
}));

export default function Register() {
    const [loading, setLoading] = useState(false);
    const [messageApi, contextHolder] = message.useMessage();

    // TSlurmDesk에서 넘겨준 redirect URL을 쿼리파라미터에서 읽음
    // 예: /register?redirect=https://tslurmdesk/dex/auth/...
    // redirect가 없으면 기본값으로 Insight 로그인 페이지 사용
    const [searchParams] = useSearchParams();
    const redirectUrl = searchParams.get('redirect') || '/login';

    const onFinish = async (values: RegisterFields) => {
        // 비밀번호 일치 확인
        if (values.password !== values.confirmPassword) {
            messageApi.error('비밀번호가 일치하지 않습니다.');
            return;
        }

        // 생년월일 조합: "1990-01-15" 형식으로 만들기
        const birth_date = `${values.birth_year}-${values.birth_month}-${values.birth_day.padStart(2, '0')}`;

        try {
            setLoading(true);

            // 백엔드 /auth/register 호출 (인증 토큰 불필요한 public 엔드포인트)
            const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: values.username,
                    password: values.password,
                    full_name: values.full_name,
                    email: values.email,
                    birth_date,
                    affiliation: values.affiliation,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                // 중복 아이디 등 에러 처리
                messageApi.error(data.detail || '가입신청 중 오류가 발생했습니다.');
                return;
            }

            // 가입신청 성공 → 팝업 → TSlurmDesk Dex 로그인 페이지로 이동
            messageApi.success('가입 신청이 완료되었습니다. Desk 등록 대기 상태입니다.');
            setTimeout(() => {
                // 외부 URL(TSlurmDesk)로 이동이므로 navigate 대신 location.href 사용
                window.location.href = redirectUrl;
            }, 1500);

        } catch {
            messageApi.error('서버 연결 중 오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-screen">
            {contextHolder}
            <div className="auth-card">
                <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 8, color: 'rgb(18, 25, 35)' }}>
                    TSlurmDesk
                </Typography.Title>
                <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}>
                    가입신청
                </Typography.Text>

                <Form<RegisterFields>
                    name="register"
                    layout="vertical"
                    onFinish={onFinish}
                    requiredMark="optional"
                    autoComplete="off"
                >
                    {/* 아이디 */}
                    <Form.Item
                        label="아이디"
                        name="username"
                        rules={[
                            { required: true, message: '아이디를 입력해 주세요.' },
                            { min: 3, message: '3자 이상 입력해 주세요.' },
                        ]}
                    >
                        <Input size="large" prefix={<UserOutlined />} placeholder="아이디" allowClear />
                    </Form.Item>

                    {/* 비밀번호 */}
                    <Form.Item
                        label="비밀번호"
                        name="password"
                        rules={[
                            { required: true, message: '비밀번호를 입력해 주세요.' },
                            { min: 4, message: '4자 이상 입력해 주세요.' },
                        ]}
                    >
                        <Input.Password size="large" prefix={<LockOutlined />} placeholder="비밀번호" />
                    </Form.Item>

                    {/* 비밀번호 재확인 */}
                    <Form.Item
                        label="비밀번호 재확인"
                        name="confirmPassword"
                        rules={[{ required: true, message: '비밀번호를 다시 입력해 주세요.' }]}
                    >
                        <Input.Password size="large" prefix={<LockOutlined />} placeholder="비밀번호 재확인" />
                    </Form.Item>

                    {/* 이름 */}
                    <Form.Item
                        label="이름"
                        name="full_name"
                        rules={[{ required: true, message: '이름을 입력해 주세요.' }]}
                    >
                        <Input size="large" placeholder="이름" allowClear />
                    </Form.Item>

                    {/* 생년월일: 년/월/일 세 개 필드 조합 */}
                    <Form.Item label="생년월일" required>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <Form.Item
                                name="birth_year"
                                noStyle
                                rules={[
                                    { required: true, message: '년도를 입력해 주세요.' },
                                    { pattern: /^\d{4}$/, message: '4자리 숫자로 입력해 주세요.' },
                                ]}
                            >
                                <Input size="large" placeholder="년(4자)" maxLength={4} style={{ width: 110 }} />
                            </Form.Item>
                            <Form.Item
                                name="birth_month"
                                noStyle
                                rules={[{ required: true, message: '월을 선택해 주세요.' }]}
                            >
                                <Select size="large" placeholder="월" style={{ width: 90 }} options={months} />
                            </Form.Item>
                            <Form.Item
                                name="birth_day"
                                noStyle
                                rules={[
                                    { required: true, message: '일을 입력해 주세요.' },
                                    { pattern: /^\d{1,2}$/, message: '숫자로 입력해 주세요.' },
                                ]}
                            >
                                <Input size="large" placeholder="일" maxLength={2} style={{ width: 80 }} />
                            </Form.Item>
                        </div>
                    </Form.Item>

                    {/* 소속 */}
                    <Form.Item
                        label="소속"
                        name="affiliation"
                        rules={[{ required: true, message: '소속을 입력해 주세요.' }]}
                    >
                        <Input size="large" prefix={<TeamOutlined />} placeholder="소속 기관 / 부서" allowClear />
                    </Form.Item>

                    {/* 이메일 */}
                    <Form.Item
                        label="이메일"
                        name="email"
                        rules={[
                            { required: true, message: '이메일을 입력해 주세요.' },
                            { type: 'email', message: '올바른 이메일 형식이 아닙니다.' },
                        ]}
                    >
                        <Input size="large" prefix={<MailOutlined />} placeholder="이메일" allowClear />
                    </Form.Item>

                    <Form.Item style={{ marginTop: 8 }}>
                        <Button type="primary" htmlType="submit" size="large" block loading={loading}>
                            가입신청
                        </Button>
                    </Form.Item>
                </Form>

                {/* 로그인 버튼: redirect URL(TSlurmDesk Dex)로 이동 */}
                <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', fontSize: 13 }}>
                    이미 계정이 있으신가요?{' '}
                    <Typography.Link onClick={() => { window.location.href = redirectUrl; }}>
                        로그인
                    </Typography.Link>
                </Typography.Text>
            </div>
        </div>
    );
}
