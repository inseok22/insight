import { useState } from 'react';
import { Button, Form, Input, Typography, message } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useProduct } from '../config/product';

type LoginFields = {
  username: string;
  password: string;
  remember?: boolean;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: number;
    username: string;
    full_name?: string | null;
    role: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function Login() {
  const [loading, setLoading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const navigate = useNavigate();
  const { product_name, home_path } = useProduct();

  const onFinish = async (values: LoginFields) => {
    try {
      setLoading(true);

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: values.username,
          password: values.password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        messageApi.error(data.detail || '아이디와 비밀번호를 다시 입력해 주세요.');
        return;
      }

      const result = data as LoginResponse;

      localStorage.setItem('token', result.access_token);
      localStorage.setItem('token_type', result.token_type);
      localStorage.setItem('user', JSON.stringify(result.user));

      messageApi.success('로그인되었습니다.');
      navigate(home_path, { replace: true });
    } catch (error) {
      console.error(error);
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
            {product_name}
          </Typography.Title>

          <Form<LoginFields>
              name="login"
              layout="vertical"
              onFinish={onFinish}
              requiredMark="optional"
              initialValues={{ remember: true }}
              autoComplete="off"
          >
            <Form.Item
                label="아이디"
                name="username"
                rules={[{ required: true, message: '아이디를 입력해 주세요.' }]}
            >
              <Input
                  size="large"
                  prefix={<UserOutlined />}
                  placeholder="아이디"
                  allowClear
                  autoComplete="username"
                  autoFocus
              />
            </Form.Item>

            <Form.Item
                label="비밀번호"
                name="password"
                rules={[{ required: true, message: '비밀번호를 입력해 주세요.' }]}
            >
              <Input.Password
                  size="large"
                  prefix={<LockOutlined />}
                  placeholder="비밀번호"
                  autoComplete="current-password"
              />
            </Form.Item>

            <Form.Item style={{ marginTop: 8 }}>
              <Button type="primary" htmlType="submit" size="large" block loading={loading}>
                로그인
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
  );
}
