import React, { useEffect, useState } from 'react'
import {
  Card, Typography, Input, Button, List, Space, Popconfirm, message, Empty, Spin, Pagination,
} from 'antd'
import {
  DeleteOutlined, UserOutlined, SendOutlined, CommentOutlined, LoginOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { commentService } from '@/services/commentService'
import { useAuth } from '@/hooks/useAuth'
import type { CommentItem } from '@/types/comment'

const { Text, Paragraph } = Typography
const { TextArea } = Input

interface Props {
  caseId: string
}

export const CommentSection: React.FC<Props> = ({ caseId }) => {
  const navigate = useNavigate()
  const { user, isAuthenticated } = useAuth()

  const [comments, setComments] = useState<CommentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [content, setContent] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 10

  const fetchComments = async (p = page) => {
    setLoading(true)
    try {
      const res = await commentService.list(caseId, p, pageSize)
      setComments(res.comments)
      setTotal(res.total)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchComments(1)
  }, [caseId])

  const handleSubmit = async () => {
    if (!isAuthenticated) {
      message.warning('请先登录后再发表评论')
      navigate('/login')
      return
    }

    const trimmed = content.trim()
    if (!trimmed) { message.warning('请输入评论内容'); return }
    if (trimmed.length > 2000) { message.warning('评论内容不能超过2000字'); return }

    setSubmitting(true)
    try {
      await commentService.create(caseId, {
        content: trimmed,
        author: user?.username || '匿名用户',
        user_id: String(user?.id || ''),
      })
      setContent('')
      message.success('评论发表成功')
      setPage(1)
      await fetchComments(1)
    } catch {
      message.error('发表失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (commentId: number) => {
    try {
      await commentService.delete(caseId, commentId)
      message.success('已删除')
      await fetchComments(page)
    } catch {
      message.error('删除失败')
    }
  }

  const handlePageChange = (p: number) => {
    setPage(p)
    fetchComments(p)
  }

  return (
    <Card
      title={
        <Space>
          <CommentOutlined />
          <span>评论区</span>
          {total > 0 && <span style={{ color: '#999', fontSize: 13 }}>（{total} 条评论）</span>}
        </Space>
      }
      style={{ borderRadius: 12, marginTop: 24 }}
    >
      {/* 发表评论 */}
      {isAuthenticated ? (
        <div style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              backgroundColor: '#1890ff', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}>
              <UserOutlined style={{ color: '#fff', fontSize: 14 }} />
            </div>
            <Text strong>{user?.username}</Text>
          </div>
          <TextArea
            placeholder="写下你的想法..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={3}
            maxLength={2000}
            showCount
            style={{ marginBottom: 12 }}
          />
          <Space>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSubmit}
              loading={submitting}
            >
              发表评论
            </Button>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {content.length}/2000
            </Text>
          </Space>
        </div>
      ) : (
        <div style={{
          marginBottom: 24, padding: '24px 0', textAlign: 'center',
          backgroundColor: '#fafafa', borderRadius: 8,
        }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
            登录后参与评论
          </Text>
          <Button type="primary" icon={<LoginOutlined />} onClick={() => navigate('/login')}>
            去登录
          </Button>
        </div>
      )}

      {/* 评论列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin />
        </div>
      ) : comments.length === 0 ? (
        <Empty description="暂无评论，来说两句吧" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <>
          <List
            dataSource={comments}
            renderItem={(item) => (
              <List.Item
                actions={[
                  isAuthenticated && String(user?.id) === item.user_id ? (
                    <Popconfirm
                      key="delete"
                      title="确定删除这条评论？"
                      onConfirm={() => handleDelete(item.id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                    </Popconfirm>
                  ) : null,
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  avatar={
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%',
                      backgroundColor: '#f0f0f0', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                    }}>
                      <UserOutlined style={{ color: '#999' }} />
                    </div>
                  }
                  title={
                    <Space>
                      <Text strong>{item.author}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {item.created_at}
                      </Text>
                    </Space>
                  }
                  description={
                    <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>
                      {item.content}
                    </Paragraph>
                  }
                />
              </List.Item>
            )}
          />
          {total > pageSize && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Pagination
                current={page}
                total={total}
                pageSize={pageSize}
                onChange={handlePageChange}
                size="small"
              />
            </div>
          )}
        </>
      )}
    </Card>
  )
}
