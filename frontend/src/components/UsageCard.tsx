import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Spin, Segmented, Empty, Typography, Progress } from 'antd'
import {
  ThunderboltOutlined, PictureOutlined, VideoCameraOutlined,
  DollarOutlined, BarChartOutlined, PieChartOutlined,
} from '@ant-design/icons'
import { usageService, type UsageSummary } from '@/services/usageService'

const { Text, Title } = Typography

interface Props {
  userId: string
}

const PERIOD_OPTIONS: Record<string, string> = {
  today: '今日',
  week: '本周',
  month: '本月',
}

const PERIOD_LABELS: Record<string, string> = {
  today: '今天',
  week: '本周',
  month: '本月',
}

const MAX_LLM_TOKENS = 1_000_000
const MAX_IMAGE_CALLS = 200
const MAX_VIDEO_CALLS = 50

// ── SVG Donut slice helper ──
const polarToCartesian = (cx: number, cy: number, r: number, angle: number) => ({
  x: cx + r * Math.cos((angle - 90) * Math.PI / 180),
  y: cy + r * Math.sin((angle - 90) * Math.PI / 180),
})

const describeArc = (cx: number, cy: number, r: number, startAngle: number, endAngle: number) => {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const large = endAngle - startAngle > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 0 ${end.x} ${end.y} L ${cx} ${cy} Z`
}

const DonutSlice: React.FC<{ color: string; start: number; end: number; cx?: number; cy?: number; r?: number }> =
  ({ color, start, end, cx = 80, cy = 80, r = 60 }) => (
    <path d={describeArc(cx, cy, r, start, end)} fill={color} opacity={0.85} />
  )

const RingSlice: React.FC<{ color: string; start: number; end: number; cx?: number; cy?: number; r?: number; width?: number }> =
  ({ color, start, end, cx = 80, cy = 80, r = 55, width = 18 }) => {
    const outer = describeArc(cx, cy, r, start, end)
    const inner = describeArc(cx, cy, r - width, end, start)
    return <path d={`${outer} ${inner} Z`} fill={color} opacity={0.9} />
  }

// ── Bar component (pure CSS) ──
const Bar: React.FC<{ pct: number; color: string; label: string; value: string; sub: string }> =
  ({ pct, color, label, value, sub }) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <Text strong style={{ fontSize: 13 }}>{label}</Text>
        <span>
          <Text strong style={{ fontSize: 14, color }}>{value}</Text>
          <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>{sub}</Text>
        </span>
      </div>
      <div style={{ height: 10, background: '#f0f0f0', borderRadius: 5, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${Math.max(pct, 2)}%`, background: color,
          borderRadius: 5, transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
        }} />
      </div>
    </div>
  )

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
      <Card style={{ marginBottom: 24 }}>
        <Empty description="请先登录" />
      </Card>
    )
  }

  const llmTokens = usage ? usage.llmTokens : 0
  const llmCalls = usage?.llmCalls ?? 0
  const llmCost = usage?.llmCost ?? 0
  const imageCalls = usage?.imageCalls ?? 0
  const imageCost = usage?.imageCost ?? 0
  const videoCalls = usage?.videoCalls ?? 0
  const videoCost = usage?.videoCost ?? 0
  const totalCost = usage?.totalCost ?? 0

  // Percentages for bars (scale to 100% for visual comparison)
  const llmPct = Math.min((llmTokens / MAX_LLM_TOKENS) * 100, 100)
  const imgPct = Math.min((imageCalls / MAX_IMAGE_CALLS) * 100, 100)
  const vidPct = Math.min((videoCalls / MAX_VIDEO_CALLS) * 100, 100)

  // Donut chart angles for cost breakdown
  const costSegments: { label: string; value: number; color: string }[] = [
    { label: 'LLM', value: llmCost, color: '#52c41a' },
    { label: '图像', value: imageCost, color: '#1890ff' },
    { label: '视频', value: videoCost, color: '#fa8c16' },
  ].filter(s => s.value > 0)
  const costTotal = costSegments.reduce((s, c) => s + c.value, 0) || 1
  let angle = 0
  const donutArcs = costSegments.map(s => {
    const sweep = (s.value / costTotal) * 360
    const arc = { ...s, start: angle, end: angle + sweep }
    angle += sweep
    return arc
  })

  // Ring progress values
  const llmRingAngle = (llmPct / 100) * 360
  const imgRingAngle = (imgPct / 100) * 360
  const vidRingAngle = (vidPct / 100) * 360

  return (
    <div style={{ marginBottom: 24 }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <BarChartOutlined style={{ marginRight: 8 }} />
          AI 用量
        </Title>
        <Segmented
          size="small"
          options={Object.entries(PERIOD_OPTIONS).map(([k, v]) => ({ label: v, value: k }))}
          value={period}
          onChange={(val) => setPeriod(val as string)}
        />
      </div>

      <Spin spinning={loading}>
        {/* ── Ring progress indicators ── */}
        <Row gutter={[24, 24]} style={{ marginBottom: 24 }}>
          {/* LLM Ring */}
          <Col xs={24} sm={8}>
            <Card variant="borderless" style={{ textAlign: 'center', background: 'linear-gradient(180deg, #f6ffed 0%, #fff 60%)' }}>
              <svg width="160" height="110" viewBox="0 0 160 110">
                <RingSlice color="#e8e8e8" start={0} end={360} cx={80} cy={75} r={48} width={14} />
                <RingSlice color="#52c41a" start={0} end={llmRingAngle} cx={80} cy={75} r={48} width={14} />
                <text x="80" y="68" textAnchor="middle" fontSize="22" fontWeight="bold" fill="#1d1d1f">
                  {(llmTokens / 1000).toFixed(0)}
                </text>
                <text x="80" y="86" textAnchor="middle" fontSize="11" fill="#8c8c8c">K tokens</text>
              </svg>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ThunderboltOutlined style={{ color: '#52c41a' }} /> 语言大模型
              </Text>
              <div style={{ marginTop: 2 }}>
                <Text style={{ fontSize: 11, color: '#8c8c8c' }}>调用 {llmCalls} 次 · ¥{llmCost.toFixed(2)}</Text>
              </div>
            </Card>
          </Col>

          {/* Image Ring */}
          <Col xs={24} sm={8}>
            <Card variant="borderless" style={{ textAlign: 'center', background: 'linear-gradient(180deg, #e6f7ff 0%, #fff 60%)' }}>
              <svg width="160" height="110" viewBox="0 0 160 110">
                <RingSlice color="#e8e8e8" start={0} end={360} cx={80} cy={75} r={48} width={14} />
                <RingSlice color="#1890ff" start={0} end={imgRingAngle} cx={80} cy={75} r={48} width={14} />
                <text x="80" y="68" textAnchor="middle" fontSize="22" fontWeight="bold" fill="#1d1d1f">
                  {imageCalls}
                </text>
                <text x="80" y="86" textAnchor="middle" fontSize="11" fill="#8c8c8c">次</text>
              </svg>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <PictureOutlined style={{ color: '#1890ff' }} /> 图像大模型
              </Text>
              <div style={{ marginTop: 2 }}>
                <Text style={{ fontSize: 11, color: '#8c8c8c' }}>¥{imageCost.toFixed(2)}</Text>
              </div>
            </Card>
          </Col>

          {/* Video Ring */}
          <Col xs={24} sm={8}>
            <Card variant="borderless" style={{ textAlign: 'center', background: 'linear-gradient(180deg, #fff7e6 0%, #fff 60%)' }}>
              <svg width="160" height="110" viewBox="0 0 160 110">
                <RingSlice color="#e8e8e8" start={0} end={360} cx={80} cy={75} r={48} width={14} />
                <RingSlice color="#fa8c16" start={0} end={vidRingAngle} cx={80} cy={75} r={48} width={14} />
                <text x="80" y="68" textAnchor="middle" fontSize="22" fontWeight="bold" fill="#1d1d1f">
                  {videoCalls}
                </text>
                <text x="80" y="86" textAnchor="middle" fontSize="11" fill="#8c8c8c">次</text>
              </svg>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <VideoCameraOutlined style={{ color: '#fa8c16' }} /> 视频大模型
              </Text>
              <div style={{ marginTop: 2 }}>
                <Text style={{ fontSize: 11, color: '#8c8c8c' }}>¥{videoCost.toFixed(2)}</Text>
              </div>
            </Card>
          </Col>
        </Row>

        {/* ── Bar comparison + Donut chart ── */}
        <Row gutter={[24, 24]}>
          {/* Bar chart — usage vs quota */}
          <Col xs={24} lg={14}>
            <Card
              title={<><BarChartOutlined /> {PERIOD_LABELS[period]}用量概览</>}
              size="small"
            >
              <Bar pct={llmPct} color="#52c41a" label="语言大模型 (LLM)"
                value={`${(llmTokens / 1000).toFixed(0)}K tokens`}
                sub={`配额 1M·${llmPct.toFixed(1)}%`} />
              <Bar pct={imgPct} color="#1890ff" label="图像大模型 (Seedream)"
                value={`${imageCalls} 次`}
                sub={`配额 200·${imgPct.toFixed(1)}%`} />
              <Bar pct={vidPct} color="#fa8c16" label="视频大模型 (Seedance)"
                value={`${videoCalls} 次`}
                sub={`配额 50·${vidPct.toFixed(1)}%`} />
            </Card>
          </Col>

          {/* Donut chart — cost breakdown */}
          <Col xs={24} lg={10}>
            <Card
              title={<><PieChartOutlined /> 费用分布</>}
              size="small"
            >
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <svg width="160" height="160" viewBox="0 0 160 160">
                  {donutArcs.length > 0 ? (
                    donutArcs.map((a, i) => (
                      <DonutSlice key={i} color={a.color} start={a.start} end={a.end} cx={80} cy={80} r={60} />
                    ))
                  ) : (
                    <DonutSlice color="#e8e8e8" start={0} end={360} cx={80} cy={80} r={60} />
                  )}
                  <circle cx="80" cy="80" r="36" fill="#fff" />
                  <text x="80" y="75" textAnchor="middle" fontSize="16" fontWeight="bold" fill="#1d1d1f">
                    ¥{totalCost.toFixed(0)}
                  </text>
                  <text x="80" y="93" textAnchor="middle" fontSize="10" fill="#8c8c8c">预估总费用</text>
                </svg>
                {/* Legend */}
                <div style={{ marginLeft: 16 }}>
                  {costSegments.map((s, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{
                        width: 10, height: 10, borderRadius: 2, background: s.color,
                        display: 'inline-block', marginRight: 6,
                      }} />
                      <Text style={{ fontSize: 12 }}>{s.label}</Text>
                      <Text strong style={{ fontSize: 13, marginLeft: 'auto', paddingLeft: 12 }}>¥{s.value.toFixed(2)}</Text>
                    </div>
                  ))}
                  {costSegments.length === 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>{PERIOD_LABELS[period]}暂无调用记录</Text>
                  )}
                </div>
              </div>
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  )
}
