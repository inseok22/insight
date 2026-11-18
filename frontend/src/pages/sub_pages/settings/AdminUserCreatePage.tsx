import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { clearAuthStorage } from '../../../utils/auth';

type AccountFields = {
  username: string;
  full_name?: string;
  password: string;
  password_confirm: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export default function AdminUserCreatePage() {
  const [form] = Form.useForm<AccountFields>();
  const [loading, setLoading] = useState(false);
  const [createdUsername, setCreatedUsername] = useState<string | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const navigate = useNavigate();

  const onFinish = async (values: AccountFields) => {
    setLoading(true);
    setCreatedUsername(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/admin/users`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          username: values.username.trim(),
          full_name: values.full_name?.trim() || null,
          password: values.password,
        }),
      });
      if (response.status === 401 || response.status === 403) {
        clearAuthStorage();
        navigate('/login', { replace: true });
        return;
      }
      const data = await response.json();
      if (!response.ok) {
        messageApi.error(typeof data.detail === 'string' ? data.detail : '사용자를 추가하지 못했습니다.');
        return;
      }
      setCreatedUsername(data.username);
      form.resetFields();
    } catch {
      messageApi.error('서버 연결을 확인한 후 다시 시도해 주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card style={{ maxWidth: 560, margin: '24px auto' }}>
      {contextHolder}
      <Typography.Title level={4}>사용자 추가</Typography.Title>
      <Typography.Paragraph type="secondary">
        추가한 계정에는 기존 관리자와 동일한 권한이 부여됩니다.
      </Typography.Paragraph>
      {createdUsername && <Alert type="success" showIcon style={{ marginBottom: 24 }}
        message={`${createdUsername} 계정이 추가되었습니다. 바로 로그인할 수 있습니다.`} />}
      <Form form={form} layout="vertical" onFinish={onFinish} autoComplete="off" disabled={loading}>
        <Form.Item name="username" label="아이디" normalize={(value: string) => value.trim()}
          extra="영문·숫자로 시작하는 1~50자이며 점(.), 밑줄(_), 하이픈(-)을 사용할 수 있습니다."
          rules={[
            { required: true, message: '아이디를 입력해 주세요.' },
            { max: 50, message: '아이디는 50자 이내로 입력해 주세요.' },
            { pattern: /^[A-Za-z0-9][A-Za-z0-9_.-]*$/, message: '아이디 형식을 확인해 주세요.' },
          ]}>
          <Input autoComplete="off" maxLength={50} />
        </Form.Item>
        <Form.Item name="full_name" label="이름" rules={[{ max: 100, message: '이름은 100자 이내로 입력해 주세요.' }]}>
          <Input autoComplete="off" maxLength={100} />
        </Form.Item>
        <Form.Item name="password" label="비밀번호" rules={[
          { required: true, message: '비밀번호를 입력해 주세요.' },
          { min: 8, max: 128, message: '비밀번호는 8~128자로 입력해 주세요.' },
        ]}>
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Form.Item name="password_confirm" label="비밀번호 확인" dependencies={['password']}
          rules={[
            { required: true, message: '비밀번호를 다시 입력해 주세요.' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                return !value || value === getFieldValue('password')
                  ? Promise.resolve() : Promise.reject(new Error('비밀번호가 일치하지 않습니다.'));
              },
            }),
          ]}>
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>사용자 추가</Button>
      </Form>
    </Card>
  );
}
