import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Typography, Button, Spin, Tag, Space, Row, Col,
  Statistic, Divider, Empty, message
} from 'antd'
import {
  ArrowLeftOutlined, EyeOutlined, LikeOutlined,
  ShareAltOutlined, PlayCircleOutlined
} from '@ant-design/icons'
import { caseService, type CaseItem } from '@/services/caseService'
import { CommentSection } from '@/components/CommentSection'

const { Title, Text, Paragraph } = Typography

export const CaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [caseData, setCaseData] = useState<CaseItem | null>(null)
  const [videoUrl, setVideoUrl] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [likes, setLikes] = useState(0)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    caseService.getCase(id)
      .then((data) => {
        setCaseData(data)
        setLikes(data.likes)
        // 从后端获取演示视频 URL
        if ((data as any).videoUrl) {
          setVideoUrl((data as any).videoUrl)
        }
        caseService.recordView(id).catch(() => {})
      })
      .catch(() => message.error('加载案例失败'))
      .finally(() => setLoading(false))
  }, [id])

  const handleLike = async () => {
    if (!id) return
    try {
      await caseService.likeCase(id)
      setLikes((prev) => prev + 1)
    } catch { /* silent */ }
  }

  const handleShare = async () => {
    if (!id) return
    try {
      await caseService.recordShare(id)
      await navigator.clipboard.writeText(window.location.href)
      message.success('链接已复制到剪贴板')
    } catch { /* silent */ }
  }

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>
  }

  if (!caseData) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Empty description="案例未找到" />
        <Button onClick={() => navigate('/')} style={{ marginTop: 16 }}>返回首页</Button>
      </div>
    )
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      {/* 顶部导航 */}
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/')}
        style={{ marginBottom: 16 }}
      >
        返回案例广场
      </Button>

      <Row gutter={[24, 24]}>
        {/* 左侧：视频播放器 */}
        <Col xs={24} lg={16}>
          <Card styles={{ body: { padding: 0 } }} style={{ overflow: 'hidden', borderRadius: 12 }}>
            {videoUrl ? (
              <video
                controls
                autoPlay
                style={{ width: '100%', display: 'block', maxHeight: 500, backgroundColor: '#000' }}
                poster={caseData.coverColor?.startsWith('http') ? caseData.coverColor : undefined}
              >
                <source src={videoUrl} type="video/mp4" />
                您的浏览器不支持视频播放
              </video>
            ) : (
              <div
                style={{
                  height: 400,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: caseData.coverColor?.startsWith('http')
                    ? undefined : `#${caseData.coverColor || '0066cc'}`,
                  backgroundImage: caseData.coverColor?.startsWith('http')
                    ? `url(${caseData.coverColor})` : undefined,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  color: 'white',
                  flexDirection: 'column',
                  gap: 16,
                }}
              >
                <PlayCircleOutlined style={{ fontSize: 64, opacity: 0.6 }} />
                <Text style={{ color: 'white', fontSize: 16, opacity: 0.6 }}>演示视频准备中</Text>
              </div>
            )}
          </Card>
        </Col>

        {/* 右侧：案例信息 */}
        <Col xs={24} lg={8}>
          <Card style={{ borderRadius: 12 }}>
            <Title level={3} style={{ marginTop: 0 }}>{caseData.title}</Title>

            <Space size={16} style={{ marginBottom: 16 }}>
              <Statistic
                value={caseData.views}
                prefix={<EyeOutlined />}
                valueStyle={{ fontSize: 18 }}
              />
              <Statistic
                value={likes}
                prefix={<LikeOutlined />}
                valueStyle={{ fontSize: 18 }}
              />
            </Space>

            <Divider style={{ margin: '12px 0' }} />

            <Text strong>作者</Text>
            <Paragraph style={{ marginBottom: 12 }}>{caseData.author}</Paragraph>

            <Text strong>简介</Text>
            <Paragraph type="secondary" style={{ fontSize: 13, lineHeight: 1.8 }}>
              {caseData.description}
            </Paragraph>

            <Divider style={{ margin: '12px 0' }} />

            <Text strong style={{ display: 'block', marginBottom: 8 }}>标签</Text>
            <Space size={[4, 8]} wrap style={{ marginBottom: 16 }}>
              {caseData.tags.map((tag, i) => (
                <Tag key={i} color="blue">{tag}</Tag>
              ))}
            </Space>

            <Space>
              <Button icon={<LikeOutlined />} onClick={handleLike}>
                点赞 {likes}
              </Button>
              <Button icon={<ShareAltOutlined />} onClick={handleShare}>
                分享
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 评论区 */}
      <CommentSection caseId={id!} />
    </div>
  )
}
