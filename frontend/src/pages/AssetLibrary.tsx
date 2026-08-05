import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Typography, Button, List, Space, Tag, Modal, Form, Input, Select,
  message, Row, Col, Tabs, Empty, Spin, Tooltip, Badge, Drawer,
} from 'antd'
import {
  UserOutlined, EnvironmentOutlined, CameraOutlined, PlusOutlined,
  StarOutlined, FireOutlined, EyeOutlined,
} from '@ant-design/icons'
import { assetService, CharacterAsset, SceneTemplate, ShotPreset } from '@/services/assetService'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const ROLE_OPTIONS = [
  { value: '主角', label: '主角', color: 'red' },
  { value: '配角', label: '配角', color: 'blue' },
  { value: '反派', label: '反派', color: 'purple' },
  { value: '群众', label: '群众', color: 'default' },
]
const SHOT_TYPES = ['全景', '中景', '近景', '特写', '大特写']
const SCENE_CATEGORIES = ['古装', '都市', '悬疑', '奇幻', '科幻', '民国', '日系']

const AssetLibrary: React.FC = () => {
  const [activeTab, setActiveTab] = useState('characters')
  const [loading, setLoading] = useState(false)
  const [characters, setCharacters] = useState<CharacterAsset[]>([])
  const [scenes, setScenes] = useState<SceneTemplate[]>([])
  const [presets, setPresets] = useState<ShotPreset[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerType, setDrawerType] = useState<'character' | 'scene' | 'preset'>('character')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form] = Form.useForm()

  // ── Load data ──
  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      if (activeTab === 'characters') {
        const res = await assetService.listCharacters({ limit: 100 })
        setCharacters((res as any)?.data || [])
      } else if (activeTab === 'scenes') {
        const res = await assetService.listScenes({ limit: 100 })
        setScenes((res as any)?.data || [])
      } else {
        const res = await assetService.listShotPresets({ limit: 100 })
        setPresets((res as any)?.data || [])
      }
    } catch (e: any) {
      // API might not be available; show empty state
      console.warn('Asset API unavailable:', e?.message)
    } finally {
      setLoading(false)
    }
  }, [activeTab])

  useEffect(() => { loadData() }, [loadData])

  // ── Create / Edit ──
  const openDrawer = (type: 'character' | 'scene' | 'preset', id?: string) => {
    setDrawerType(type)
    setEditingId(id || null)
    form.resetFields()
    if (id) {
      // Pre-populate for edit (simplified — just set existing data)
      const item = type === 'character'
        ? characters.find(c => c.asset_id === id)
        : type === 'scene'
          ? scenes.find(s => s.template_id === id)
          : presets.find(p => p.preset_id === id)
      if (item) form.setFieldsValue(item as any)
    }
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    try {
      if (drawerType === 'character') {
        if (editingId) {
          await assetService.updateCharacter(editingId, values)
        } else {
          await assetService.createCharacter(values)
        }
      } else if (drawerType === 'scene') {
        await assetService.createScene(values)
      } else {
        await assetService.createShotPreset(values)
      }
      message.success(editingId ? '已更新' : '已创建')
      setDrawerOpen(false)
      loadData()
    } catch (e: any) {
      message.error(`保存失败: ${e?.message || e}`)
    }
  }

  // ── Render helpers ──
  const roleTag = (role: string) => {
    const opt = ROLE_OPTIONS.find(o => o.value === role)
    return <Tag color={opt?.color || 'default'}>{role}</Tag>
  }

  const shotTypeTag = (t: string) => {
    const colors: Record<string, string> = { '全景': 'green', '中景': 'blue', '近景': 'orange', '特写': 'red', '大特写': 'purple' }
    return <Tag color={colors[t] || 'default'}>{t}</Tag>
  }

  // ── Drawer form ──
  const renderForm = () => {
    if (drawerType === 'character') {
      return <>
        <Form.Item name="name" label="角色名" rules={[{ required: true }]}><Input /></Form.Item>
        <Row gutter={12}>
          <Col span={8}><Form.Item name="role_type" label="定位" initialValue="配角"><Select options={ROLE_OPTIONS} /></Form.Item></Col>
          <Col span={8}><Form.Item name="gender" label="性别"><Select options={[{ value: '男', label: '男' }, { value: '女', label: '女' }]} /></Form.Item></Col>
          <Col span={8}><Form.Item name="age_range" label="年龄段"><Select options={['少年', '青年', '中年', '老年'].map(v => ({ value: v, label: v }))} /></Form.Item></Col>
        </Row>
        <Form.Item name="appearance" label="外貌描述" rules={[{ required: true }]} help="越详细越好，会用做 AI 生成参考图"><TextArea rows={3} /></Form.Item>
        <Form.Item name="clothing_style" label="服装风格"><Input placeholder="白色长袍、腰间玉带" /></Form.Item>
        <Form.Item name="distinctive_features" label="辨识特征" help="逗号分隔，如：左眼角泪痣, 银色长发"><Select mode="tags" placeholder="输入后回车" /></Form.Item>
        <Form.Item name="tags" label="标签"><Select mode="tags" placeholder="古装, 仙侠, 高冷" /></Form.Item>
      </>
    }
    if (drawerType === 'scene') {
      return <>
        <Form.Item name="name" label="模板名称" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="category" label="分类" rules={[{ required: true }]}><Select options={SCENE_CATEGORIES.map(v => ({ value: v, label: v }))} /></Form.Item>
        <Form.Item name="location_description" label="场景描述" rules={[{ required: true }]} help="AI prompt 用"><TextArea rows={3} /></Form.Item>
        <Form.Item name="lighting_style" label="灯光风格"><Input placeholder="三点布光" /></Form.Item>
        <Form.Item name="tags" label="标签"><Select mode="tags" placeholder="室内, 白天, 温馨" /></Form.Item>
      </>
    }
    return <>
      <Form.Item name="name" label="预设名称" rules={[{ required: true }]}><Input /></Form.Item>
      <Row gutter={12}>
        <Col span={12}><Form.Item name="shot_type" label="镜头类型" rules={[{ required: true }]}><Select options={SHOT_TYPES.map(v => ({ value: v, label: v }))} /></Form.Item></Col>
        <Col span={12}><Form.Item name="camera_angle" label="机位角度"><Input placeholder="平视" /></Form.Item></Col>
      </Row>
      <Row gutter={12}>
        <Col span={12}><Form.Item name="camera_movement" label="运镜方式"><Input placeholder="固定" /></Form.Item></Col>
        <Col span={12}><Form.Item name="focal_length" label="焦段"><Input placeholder="50mm" /></Form.Item></Col>
      </Row>
      <Form.Item name="composition_rule" label="构图法则"><Input placeholder="三分法" /></Form.Item>
      <Form.Item name="description" label="使用场景说明"><TextArea rows={2} /></Form.Item>
    </>
  }

  // ── Main render ──
  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={3} style={{ margin: 0 }}>资产库</Title>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openDrawer(activeTab === 'scenes' ? 'scene' : activeTab === 'presets' ? 'preset' : 'character')}>
            新建{activeTab === 'scenes' ? '场景' : activeTab === 'presets' ? '分镜预设' : '角色'}
          </Button>
        </Space>
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
        {
          key: 'characters',
          label: <span><UserOutlined /> 角色资产 ({characters.length})</span>,
          children: (
            <Spin spinning={loading}>
              {characters.length === 0 ? <Empty description="暂无角色资产，点击上方按钮创建" /> : (
                <List
                  grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                  dataSource={characters}
                  renderItem={(item: CharacterAsset) => (
                    <List.Item>
                      <Card
                        hoverable
                        size="small"
                        onClick={() => openDrawer('character', item.asset_id)}
                        title={<Space>{item.name}{roleTag(item.role_type)}</Space>}
                        extra={<Text type="secondary" style={{ fontSize: 11 }}>引用 {item.usage_count}</Text>}
                      >
                        <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
                          {item.appearance}
                        </Paragraph>
                        <Space size={4} wrap>
                          {item.tags?.slice(0, 4).map((t: string) => <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>)}
                          {item.avg_quality_score > 0 && (
                            <Tooltip title="平均质量分"><Tag color="gold" style={{ fontSize: 11 }}><StarOutlined /> {item.avg_quality_score.toFixed(1)}</Tag></Tooltip>
                          )}
                        </Space>
                      </Card>
                    </List.Item>
                  )}
                />
              )}
            </Spin>
          ),
        },
        {
          key: 'scenes',
          label: <span><EnvironmentOutlined /> 场景模板 ({scenes.length})</span>,
          children: (
            <Spin spinning={loading}>
              {scenes.length === 0 ? <Empty description="暂无场景模板" /> : (
                <List
                  grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                  dataSource={scenes}
                  renderItem={(item: SceneTemplate) => (
                    <List.Item>
                      <Card hoverable size="small" title={item.name}
                        extra={<Tag>{item.category}</Tag>}
                      >
                        <Paragraph ellipsis={{ rows: 2 }} type="secondary" style={{ fontSize: 12 }}>
                          {item.location_description}
                        </Paragraph>
                        <Space size={4}>
                          {item.lighting_setup?.style && <Tag color="orange">{item.lighting_setup.style}</Tag>}
                          <Tag>{item.usage_count} 次引用</Tag>
                        </Space>
                      </Card>
                    </List.Item>
                  )}
                />
              )}
            </Spin>
          ),
        },
        {
          key: 'presets',
          label: <span><CameraOutlined /> 分镜预设 ({presets.length})</span>,
          children: (
            <Spin spinning={loading}>
              {presets.length === 0 ? <Empty description="暂无分镜预设" /> : (
                <List
                  grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }}
                  dataSource={presets}
                  renderItem={(item: ShotPreset) => (
                    <List.Item>
                      <Card hoverable size="small" title={item.name}
                        extra={shotTypeTag(item.shot_type)}
                      >
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Text style={{ fontSize: 12 }}>机位: {item.camera_angle || '-'} | 运镜: {item.camera_movement || '-'}</Text>
                          <Text style={{ fontSize: 12 }}>焦段: {item.focal_length || '-'} | 构图: {item.composition_rule || '-'}</Text>
                          {item.description && <Paragraph ellipsis={{ rows: 1 }} type="secondary" style={{ fontSize: 11, margin: 0 }}>{item.description}</Paragraph>}
                          <Tag>{item.usage_count} 次引用</Tag>
                        </Space>
                      </Card>
                    </List.Item>
                  )}
                />
              )}
            </Spin>
          ),
        },
      ]} />

      {/* Create/Edit Drawer */}
      <Drawer
        title={`${editingId ? '编辑' : '新建'}${drawerType === 'character' ? '角色' : drawerType === 'scene' ? '场景' : '分镜预设'}`}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={500}
        extra={<Button type="primary" onClick={handleSave}>保存</Button>}
      >
        <Form form={form} layout="vertical">{renderForm()}</Form>
      </Drawer>
    </div>
  )
}

export default AssetLibrary
