import React, { useState } from 'react'
import { Form, Input, Button, Card, Typography, Space, Divider } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { LoginRequest } from '@/types'

const { Title, Text } = Typography

const Login: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  // 如果已登录，直接跳转
  React.useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as any)?.from || '/'
      navigate(from, { replace: true })
    }
  }, [isAuthenticated])

  const handleSubmit = async (values: LoginRequest) => {
    setLoading(true)
    try {
      await login(values)
      // 登录成功后跳转到之前的页面，或首页
      const from = (location.state as any)?.from || '/'
      navigate(from, { replace: true })
    } catch {
      // 错误已在 useAuth hook 中处理
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: 'calc(100vh - 64px)',
        padding: '24px',
      }}
    >
      <Card
        style={{
          width: '100%',
          maxWidth: 420,
          borderRadius: 12,
          boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
        }}
        styles={{ body: { padding: '40px 32px' } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2} style={{ marginBottom: 8 }}>
            登录
          </Title>
          <Text type="secondary">欢迎回到拓扑漫剧平台</Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
            ]}
          >
            <Input
              prefix={<UserOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="用户名"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 12 }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44 }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <Divider plain>
          <Text type="secondary" style={{ fontSize: 13 }}>
            还没有账户？
          </Text>
        </Divider>

        <div style={{ textAlign: 'center' }}>
          <Space>
            <Text>还没有账户？</Text>
            <Link
              to="/register"
              style={{ color: '#0066cc', fontWeight: 500 }}
            >
              立即注册
            </Link>
          </Space>
        </div>
      </Card>
    </div>
  )
}

export default Login
