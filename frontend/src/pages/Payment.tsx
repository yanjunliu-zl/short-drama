import React, { useState, useEffect } from 'react'
import {
  Card, Tabs, Form, Input, Button, Select, Typography, Space, Descriptions,
  Tag, List, message, Statistic, Row, Col, Divider, Modal, QRCode
} from 'antd'
import {
  WalletOutlined, WechatOutlined, AlipayCircleOutlined,
  HistoryOutlined, DollarOutlined, ReloadOutlined
} from '@ant-design/icons'
import { useAuth } from '@/hooks/useAuth'
import { paymentService, type PaymentOrder, type CreatePaymentParams } from '@/services/paymentService'
import { UsageCard } from '@/components/UsageCard'

const { Title, Text } = Typography

// 订阅计划
const SUBSCRIPTION_PLANS = [
  {
    id: 'basic',
    name: '基础版',
    price: 29.9,
    period: '月',
    features: ['每月10个剧本', '每月5个视频', '基础AI模型', '社区支持'],
    color: '#0066cc',
  },
  {
    id: 'pro',
    name: '专业版',
    price: 99.9,
    period: '月',
    features: ['每月50个剧本', '每月20个视频', '高级AI模型', '优先处理', '优先支持'],
    color: '#0066cc',
    isPopular: true,
  },
  {
    id: 'enterprise',
    name: '企业版',
    price: 299.9,
    period: '月',
    features: ['无限剧本', '无限视频', '顶级AI模型', '专属客服', 'API接入', '自定义品牌'],
    color: '#007aff',
  },
]

const CREDIT_PACKAGES = [
  { id: 'credit_100', name: '100积分', price: 10, credits: 100, color: '#0066cc' },
  { id: 'credit_500', name: '500积分', price: 45, credits: 500, color: '#34c759', tag: '热门' },
  { id: 'credit_1000', name: '1000积分', price: 80, credits: 1000, color: '#0066cc', tag: '推荐' },
  { id: 'credit_5000', name: '5000积分', price: 350, credits: 5000, color: '#007aff', tag: '超值' },
]

const Payment: React.FC = () => {
  const { user, isAuthenticated } = useAuth()
  const [activeTab, setActiveTab] = useState('subscription')
  const [paymentModal, setPaymentModal] = useState(false)
  const [selectedPlan, setSelectedPlan] = useState<any>(null)
  const [selectedCredit, setSelectedCredit] = useState<any>(null)
  const [paymentMethod, setPaymentMethod] = useState<'wechat' | 'alipay'>('wechat')
  const [customAmount, setCustomAmount] = useState<number>(0)
  const [currentPayment, setCurrentPayment] = useState<PaymentOrder | null>(null)
  const [paymentHistory, setPaymentHistory] = useState<PaymentOrder[]>([])
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [form] = Form.useForm()

  // 加载支付历史
  const loadPaymentHistory = async () => {
    if (!user) return
    setHistoryLoading(true)
    try {
      const res = await paymentService.listPayments({
        user_id: String(user.id),
        page: 1,
        pageSize: 20,
      })
      setPaymentHistory(res.payments || [])
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false)
    }
  }

  useEffect(() => {
    loadPaymentHistory()
  }, [user])

  // 打开订阅支付弹窗
  const openSubscriptionPayment = (plan: any) => {
    setSelectedPlan(plan)
    setSelectedCredit(null)
    setCurrentPayment(null)
    setPaymentModal(true)
  }

  // 打开积分支付弹窗
  const openCreditPayment = (credit: any) => {
    setSelectedCredit(credit)
    setSelectedPlan(null)
    setCurrentPayment(null)
    setPaymentModal(true)
  }

  // 打开自定义金额支付
  const openCustomPayment = () => {
    if (!customAmount || customAmount <= 0) {
      message.warning('请输入有效金额')
      return
    }
    setSelectedPlan({ id: 'custom', name: '自定义充值', price: customAmount, period: '' })
    setSelectedCredit(null)
    setCurrentPayment(null)
    setPaymentModal(true)
  }

  // 执行支付
  const handlePayment = async () => {
    if (!user || !isAuthenticated) {
      message.error('请先登录')
      return
    }

    const target = selectedPlan || selectedCredit
    if (!target) return

    setLoading(true)
    try {
      const params: CreatePaymentParams = {
        order_no: `ORD_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
        user_id: String(user.id),
        amount: Math.round(target.price * 100), // 元转分
        currency: 'CNY',
        method: paymentMethod,
        subject: target.name || '充值',
        description: selectedPlan ? `订阅${target.name}` : `购买${target.credits || 0}积分`,
      }

      const res = await paymentService.createPayment(params)
      if (res.success && res.data) {
        setCurrentPayment(res.data)
        message.success('支付订单已创建')
        loadPaymentHistory()
      } else {
        message.error(res.message || '创建支付订单失败')
      }
    } catch (err: any) {
      message.error(err?.message || '支付失败')
    } finally {
      setLoading(false)
    }
  }

  // 轮询支付状态
  const checkPaymentStatus = async () => {
    if (!currentPayment) return
    try {
      const res = await paymentService.getPayment(currentPayment.id)
      if (res.success && res.data) {
        setCurrentPayment(res.data)
        if (res.data.status === 'paid') {
          message.success('支付成功！')
          setPaymentModal(false)
          loadPaymentHistory()
        }
      }
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (currentPayment?.status === 'pending') {
      const timer = setInterval(checkPaymentStatus, 3000)
      return () => clearInterval(timer)
    }
  }, [currentPayment?.status])

  const statusColorMap: Record<string, string> = {
    pending: 'orange', paid: 'green', failed: 'red',
    canceled: 'default', refunded: 'blue',
  }
  const statusLabelMap: Record<string, string> = {
    pending: '待支付', paid: '已支付', failed: '失败',
    canceled: '已取消', refunded: '已退款',
  }

  const methodIconMap = {
    wechat: <WechatOutlined style={{ color: '#07c160', fontSize: 18 }} />,
    alipay: <AlipayCircleOutlined style={{ color: '#0066cc', fontSize: 18 }} />,
  }
  const methodLabelMap = { wechat: '微信支付', alipay: '支付宝' }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}><WalletOutlined style={{ marginRight: 12 }} />支付中心</Title>

      {/* AI 用量卡片 */}
      <UsageCard userId={String(user.id)} />

      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        选择订阅计划或购买积分，解锁更多创作功能
      </Text>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="large"
        style={{ marginBottom: 24 }}
        items={[
          { label: '订阅计划', key: 'subscription' },
          { label: '积分充值', key: 'credits' },
          { label: '支付记录', key: 'history' },
        ]}
      />

      {activeTab === 'subscription' && (
        <Row gutter={[24, 24]}>
          {SUBSCRIPTION_PLANS.map(plan => (
            <Col xs={24} sm={8} key={plan.id}>
              <Card
                hoverable
                style={{
                  borderRadius: 12,
                  borderColor: plan.isPopular ? plan.color : undefined,
                  borderWidth: plan.isPopular ? 2 : 1,
                }}
                title={
                  <div style={{ textAlign: 'center' }}>
                    <Text strong style={{ fontSize: 18 }}>{plan.name}</Text>
                    {plan.isPopular && (
                      <Tag color={plan.color} style={{ marginLeft: 8 }}>热门</Tag>
                    )}
                  </div>
                }
              >
                <div style={{ textAlign: 'center', marginBottom: 16 }}>
                  <Statistic
                    value={plan.price}
                    prefix="¥"
                    suffix={`/ ${plan.period}`}
                    valueStyle={{ color: plan.color, fontSize: 36 }}
                  />
                </div>
                <List
                  size="small"
                  dataSource={plan.features}
                  renderItem={item => (
                    <List.Item style={{ border: 'none', padding: '4px 0' }}>
                      <Text type="secondary">✓ {item}</Text>
                    </List.Item>
                  )}
                />
                <Button
                  type={plan.isPopular ? 'primary' : 'default'}
                  block
                  size="large"
                  style={{ marginTop: 16, borderRadius: 8 }}
                  onClick={() => openSubscriptionPayment(plan)}
                >
                  立即订阅
                </Button>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {activeTab === 'credits' && (
        <>
          <Row gutter={[24, 24]}>
            {CREDIT_PACKAGES.map(pkg => (
              <Col xs={24} sm={6} key={pkg.id}>
                <Card
                  hoverable
                  style={{ borderRadius: 12, textAlign: 'center' }}
                  title={
                    <div>
                      <Text strong style={{ fontSize: 16 }}>{pkg.name}</Text>
                      {pkg.tag && <Tag color={pkg.color} style={{ marginLeft: 8 }}>{pkg.tag}</Tag>}
                    </div>
                  }
                >
                  <Statistic value={pkg.price} prefix="¥" valueStyle={{ color: pkg.color }} />
                  <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                    约 ¥{(pkg.price / pkg.credits).toFixed(2)}/积分
                  </Text>
                  <Button
                    type="primary"
                    block
                    size="large"
                    style={{ marginTop: 16, borderRadius: 8 }}
                    onClick={() => openCreditPayment(pkg)}
                  >
                    立即购买
                  </Button>
                </Card>
              </Col>
            ))}
          </Row>

          <Divider>自定义金额</Divider>
          <Card style={{ maxWidth: 400, margin: '0 auto', borderRadius: 12 }}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                type="number"
                prefix="¥"
                placeholder="输入充值金额"
                value={customAmount || ''}
                onChange={e => setCustomAmount(Number(e.target.value))}
                style={{ borderRadius: '8px 0 0 8px' }}
              />
              <Button type="primary" onClick={openCustomPayment} style={{ borderRadius: '0 8px 8px 0' }}>
                充值
              </Button>
            </Space.Compact>
          </Card>
        </>
      )}

      {activeTab === 'history' && (
        <Card style={{ borderRadius: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Text strong>支付记录</Text>
            <Button icon={<ReloadOutlined />} onClick={loadPaymentHistory} loading={historyLoading}>
              刷新
            </Button>
          </div>
          <List
            loading={historyLoading}
            dataSource={paymentHistory}
            locale={{ emptyText: '暂无支付记录' }}
            renderItem={item => (
              <List.Item
                actions={[
                  <Tag key="status" color={statusColorMap[item.status]}>
                    {statusLabelMap[item.status]}
                  </Tag>,
                  item.status === 'pending' && (
                    <Button key="check" size="small" onClick={() => {
                      setCurrentPayment(item)
                      setPaymentModal(true)
                    }}>查看</Button>
                  ),
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  avatar={methodIconMap[item.method as keyof typeof methodIconMap]}
                  title={
                    <Space>
                      <Text strong>{item.subject}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>#{item.order_no}</Text>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" size={0}>
                      <Text type="secondary">{methodLabelMap[item.method as keyof typeof methodLabelMap]}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.created_at}
                      </Text>
                    </Space>
                  }
                />
                <Text strong style={{ color: '#1d1d1f', marginRight: 16 }}>
                  ¥{(item.amount / 100).toFixed(2)}
                </Text>
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 支付弹窗 */}
      <Modal
        title="确认支付"
        open={paymentModal}
        onCancel={() => { setPaymentModal(false); setCurrentPayment(null) }}
        footer={currentPayment?.status === 'pending' ? null : undefined}
        width={480}
      >
        {(selectedPlan || selectedCredit) && !currentPayment && (
          <>
            <Descriptions column={1} style={{ marginBottom: 16 }}>
              <Descriptions.Item label="商品">
                {selectedPlan?.name || selectedCredit?.name}
              </Descriptions.Item>
              <Descriptions.Item label="金额">
                <Text strong style={{ fontSize: 18, color: '#1d1d1f' }}>
                  ¥{(selectedPlan?.price || selectedCredit?.price || 0).toFixed(2)}
                </Text>
              </Descriptions.Item>
              {selectedPlan?.period && (
                <Descriptions.Item label="周期">每{selectedPlan.period}</Descriptions.Item>
              )}
              {selectedCredit?.credits && (
                <Descriptions.Item label="获得积分">{selectedCredit.credits}</Descriptions.Item>
              )}
            </Descriptions>

            <Form.Item label="支付方式" style={{ marginBottom: 16 }}>
              <Select
                value={paymentMethod}
                onChange={setPaymentMethod}
                style={{ width: '100%' }}
                options={[
                  { value: 'wechat', label: '微信支付' },
                  { value: 'alipay', label: '支付宝' },
                ]}
              />
            </Form.Item>

            <Button
              type="primary"
              block
              size="large"
              loading={loading}
              onClick={handlePayment}
              style={{ borderRadius: 8, height: 48 }}
              icon={methodIconMap[paymentMethod]}
            >
              使用{methodLabelMap[paymentMethod]}支付 ¥{(selectedPlan?.price || selectedCredit?.price || 0).toFixed(2)}
            </Button>
          </>
        )}

        {currentPayment && currentPayment.status === 'pending' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Title level={4}>请扫码支付</Title>
            {currentPayment.qr_code ? (
              <QRCode value={currentPayment.qr_code} size={200} style={{ margin: '16px auto' }} />
            ) : (
              <div style={{
                width: 200, height: 200, margin: '16px auto',
                background: '#fafafa', borderRadius: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexDirection: 'column',
              }}>
                {methodIconMap[currentPayment.method as keyof typeof methodIconMap]}
                <Text style={{ marginTop: 8 }}>
                  {methodLabelMap[currentPayment.method as keyof typeof methodLabelMap]}
                </Text>
              </div>
            )}
            <Descriptions column={1} style={{ marginTop: 16 }}>
              <Descriptions.Item label="订单号">{currentPayment.order_no}</Descriptions.Item>
              <Descriptions.Item label="金额">
                <Text strong>¥{(currentPayment.amount / 100).toFixed(2)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color="orange">等待支付</Tag>
              </Descriptions.Item>
            </Descriptions>
            <Text type="secondary">支付状态自动检测中...</Text>
          </div>
        )}

        {currentPayment && currentPayment.status === 'paid' && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <DollarOutlined style={{ fontSize: 48, color: '#34c759' }} />
            <Title level={4} style={{ color: '#34c759' }}>支付成功！</Title>
            <Text>订单号: {currentPayment.order_no}</Text>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default Payment
