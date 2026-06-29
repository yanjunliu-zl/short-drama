import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Progress, Typography, Spin, Segmented, Empty } from 'antd'
import { ThunderboltOutlined, PictureOutlined, VideoCameraOutlined, DollarOutlined } from '@ant-design/icons'
import { usageService, type UsageSummary } from '@/services/usageService'

const { Text } = Typography

interface Props {
  userId: string
}

const PERIOD_OPTIONS: Record<string, string> = {
  today: '今日',
  week: '本周',
  month: '本月',
}

const MAX_LLM_TOKENS = 1_000_000    // 月配额 100 万 token
const MAX_IMAGE_CALLS = 200          // 月配额 200 次
const MAX_VIDEO_CALLS = 50           // 月配额 50 次

export const UsageCard: React.FC<Props> = ({ userId }) => {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [period, setPeriod] = useState<string>('month')

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    usageService.getSummary(userId, period)
      .then(setUsage)
      .catch(() => setUsage(null))
      .finally(() => setLoading(false))
  }, [userId, period])

  if (!userId) {
    return (
      <Card title="AI 用量" style={{ marginBottom: 24 }}>
        <Empty description="请先登录" />
      </Card>
    )
  }

  const llmPercent = usage ? Math.min((usage.llmTokens / MAX_LLM_TOKENS) * 100, 100) : 0
  const imagePercent = usage ? Math.min((usage.imageCalls / MAX_IMAGE_CALLS) * 100, 100) : 0
  const videoPercent = usage ? Math.min((usage.videoCalls / MAX_VIDEO_CALLS) * 100, 100) : 0

  return (
    <Card
      title="AI 用量"
      extra={
        <Segmented
          size="small"
          options={Object.entries(PERIOD_OPTIONS).map(([k, v]) => ({ label: v, value: k }))}
          value={period}
          onChange={(val) => setPeriod(val as string)}
        />
      }
      style={{ marginBottom: 24 }}
    >
      <Spin spinning={loading}>
        <Row gutter={[24, 24]}>
          {/* 大语言模型 */}
          <Col xs={24} sm={8}>
            <Card size="small" variant="borderless" style={{ background: '#f6ffed' }}>
              <Statistic
                title={<><ThunderboltOutlined style={{ color: '#52c41a' }} /> 语言大模型 (DeepSeek)</>}
                value={usage ? (usage.llmTokens / 1000).toFixed(0) : '-'}
                suffix="K tokens"
                valueStyle={{ fontSize: 22 }}
              />
              <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                调用 {usage?.llmCalls ?? 0} 次 · 预估 ¥{usage?.llmCost?.toFixed(2) ?? '0.00'}
              </Text>
              <Progress
                percent={llmPercent}
                status={llmPercent > 90 ? 'exception' : 'active'}
                size="small"
                style={{ marginTop: 8 }}
                format={() => `${llmPercent.toFixed(1)}%`}
              />
              <Text type="secondary" style={{ fontSize: 11 }}>月配额 100 万 token</Text>
            </Card>
          </Col>

          {/* 图像大模型 */}
          <Col xs={24} sm={8}>
            <Card size="small" variant="borderless" style={{ background: '#e6f7ff' }}>
              <Statistic
                title={<><PictureOutlined style={{ color: '#1890ff' }} /> 图像大模型 (Seedream)</>}
                value={usage?.imageCalls ?? '-'}
                suffix="次"
                valueStyle={{ fontSize: 22 }}
              />
              <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                预估 ¥{usage?.imageCost?.toFixed(2) ?? '0.00'}
              </Text>
              <Progress
                percent={imagePercent}
                status={imagePercent > 90 ? 'exception' : 'active'}
                size="small"
                style={{ marginTop: 8 }}
                format={() => `${imagePercent.toFixed(1)}%`}
              />
              <Text type="secondary" style={{ fontSize: 11 }}>月配额 200 次</Text>
            </Card>
          </Col>

          {/* 视频大模型 */}
          <Col xs={24} sm={8}>
            <Card size="small" variant="borderless" style={{ background: '#fff7e6' }}>
              <Statistic
                title={<><VideoCameraOutlined style={{ color: '#fa8c16' }} /> 视频大模型 (Seedance)</>}
                value={usage?.videoCalls ?? '-'}
                suffix="次"
                valueStyle={{ fontSize: 22 }}
              />
              <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                预估 ¥{usage?.videoCost?.toFixed(2) ?? '0.00'}
              </Text>
              <Progress
                percent={videoPercent}
                status={videoPercent > 90 ? 'exception' : 'active'}
                size="small"
                style={{ marginTop: 8 }}
                format={() => `${videoPercent.toFixed(1)}%`}
              />
              <Text type="secondary" style={{ fontSize: 11 }}>月配额 50 次</Text>
            </Card>
          </Col>
        </Row>

        {/* 总计行 */}
        {usage && (
          <Row style={{ marginTop: 16 }}>
            <Col span={24} style={{ textAlign: 'right' }}>
              <DollarOutlined />{' '}
              <Text strong style={{ fontSize: 16 }}>
                预估总费用：¥{usage.totalCost.toFixed(2)}
              </Text>
              <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                （仅供参考，以实际账单为准）
              </Text>
            </Col>
          </Row>
        )}
      </Spin>
    </Card>
  )
}
