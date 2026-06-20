import React, { useState } from 'react'
import { Form, Input, Button, Card, Typography, Space, Divider } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined, PhoneOutlined } from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import type { RegisterRequest } from '@/types'

const { Title, Text } = Typography

const Register: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (values: RegisterRequest & { confirmPassword: string }) => {
    setLoading(true)
    try {
      await register({
        username: values.username,
        email: values.email,
        password: values.password,
        phone: values.phone,
      })
      navigate('/')
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
            注册
          </Title>
          <Text type="secondary">创建您的拓扑漫剧平台账户</Text>
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
              { max: 50, message: '用户名最多50个字符' },
              {
                pattern: /^[a-zA-Z0-9_一-龥]+$/,
                message: '用户名只能包含字母、数字、下划线和中文',
              },
            ]}
          >
            <Input
              prefix={<UserOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="用户名"
            />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input
              prefix={<MailOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="邮箱"
            />
          </Form.Item>

          <Form.Item
            name="phone"
            rules={[
              { required: false, message: '请输入手机号' },
              {
                pattern: /^1[3-9]\d{9}$/,
                message: '请输入有效的手机号',
              },
            ]}
          >
            <Input
              prefix={<PhoneOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="手机号（选填）"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
              { max: 50, message: '密码最多50个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: '#aeaeb2' }} />}
              placeholder="确认密码"
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
              注册
            </Button>
          </Form.Item>
        </Form>

        <Divider plain>
          <Text type="secondary" style={{ fontSize: 13 }}>
            已有账户？
          </Text>
        </Divider>

        <div style={{ textAlign: 'center' }}>
          <Space>
            <Text>已有账户？</Text>
            <Link
              to="/login"
              style={{ color: '#0066cc', fontWeight: 500 }}
            >
              立即登录
            </Link>
          </Space>
        </div>
      </Card>
    </div>
  )
}

export default Register
