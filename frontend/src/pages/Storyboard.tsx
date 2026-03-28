import React, { useState } from 'react';
import {
  Card,
  Typography,
  Button,
  List,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Row,
  Col,
  Drawer,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  CameraOutlined,
  VideoCameraOutlined,
  SoundOutlined,
  ClockCircleOutlined,
  FolderOpenOutlined,
  StarOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

// 分镜头类型定义
interface Shot {
  id: number;
  number: number; // 镜头编号
  shotType: string; // 镜头类型：远景、中景、近景、特写
  duration: number; // 时长（秒）
  cameraAngle: string; // 摄像机角度
  sceneRef: string; // 关联的场景
  characters: string[]; // 出场的角色
  description: string; // 画面描述
  dialogue: string; // 对白/旁白
  soundEffects: string[]; // 音效
  music: string; // 背景音乐
  notes: string; // 备注
}

// 集数类型定义
interface Episode {
  id: string;
  title: string;
  number: number;
  shots: Shot[];
  description?: string;
}

const Storyboard: React.FC = () => {
  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([
    {
      id: 'ep-1',
      title: '第一集',
      number: 1,
      shots: [
        {
          id: 1,
          number: 1,
          shotType: '远景',
          duration: 5,
          cameraAngle: '正面平视',
          sceneRef: '现代咖啡馆',
          characters: ['李明', '张薇'],
          description: '咖啡馆全景，顾客稀疏，阳光透过窗户洒进来',
          dialogue: '',
          soundEffects: ['环境音', '咖啡机声'],
          music: '轻柔的钢琴曲',
          notes: '突出咖啡馆的温馨氛围',
        },
        {
          id: 2,
          number: 2,
          shotType: '中景',
          duration: 8,
          cameraAngle: '正面平视',
          sceneRef: '现代咖啡馆',
          characters: ['李明'],
          description: '李明走进咖啡馆，四处张望，表情有些紧张',
          dialogue: '李明：（自言自语）希望她没有走错地方',
          soundEffects: ['脚步声', '门铃声'],
          music: '轻柔的钢琴曲',
          notes: '突出李明紧张的情绪',
        },
        {
          id: 3,
          number: 3,
          shotType: '近景',
          duration: 6,
          cameraAngle: '正面平视',
          sceneRef: '现代咖啡馆',
          characters: ['张薇'],
          description: '张薇坐在角落看书，阳光洒在她身上，专注而安静',
          dialogue: '',
          soundEffects: ['翻书声'],
          music: '轻柔的钢琴曲',
          notes: '突出张薇的优雅气质',
        },
        {
          id: 4,
          number: 4,
          shotType: '特写',
          duration: 4,
          cameraAngle: '俯视',
          sceneRef: '现代咖啡馆',
          characters: ['李明', '张薇'],
          description: '两人对视的特写镜头，李明略显紧张，张薇微笑回应',
          dialogue: '张薇：你好，我能坐这里吗？',
          soundEffects: [],
          music: '音乐渐强',
          notes: '突出眼神交流',
        },
      ],
      description: '故事的开端，主角相遇',
    },
  ]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  // 编辑状态
  const [editingShot, setEditingShot] = useState<Shot | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 获取当前集数的数据
  const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);
  const currentShots = currentEpisode?.shots || [];

  // 集数操作
  const handleAddEpisode = () => {
    const newEpisode: Episode = {
      id: `ep-${Date.now()}`,
      title: `第${episodes.length + 1}集`,
      number: episodes.length + 1,
      shots: [],
      description: '新集数',
    };
    setEpisodes([...episodes, newEpisode]);
    setActiveEpisodeId(newEpisode.id);
    message.success(`已添加 ${newEpisode.title}`);
  };

  const handleEditEpisode = (episode: Episode) => {
    setEditingEpisode(episode);
    setIsDrawerOpen(true);
  };

  const handleDeleteEpisode = (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这集吗？删除后内容将无法恢复。',
      onOk: () => {
        const filtered = episodes.filter(ep => ep.id !== id);
        if (filtered.length > 0) {
          const newActiveId = id === activeEpisodeId ? filtered[0].id : activeEpisodeId;
          setActiveEpisodeId(newActiveId);
        }
        setEpisodes(filtered);
        message.success('集数已删除');
      },
    });
  };

  const handleSaveEpisode = (values: any) => {
    if (editingEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === editingEpisode.id ? { ...ep, ...values } : ep
      );
      setEpisodes(updatedEpisodes);
      message.success('集数信息已更新');
      setIsDrawerOpen(false);
      setEditingEpisode(null);
    }
  };

  // 分镜头操作
  const handleAddShot = () => {
    const newShot: Shot = {
      id: Date.now(),
      number: currentShots.length + 1,
      shotType: '中景',
      duration: 5,
      cameraAngle: '正面平视',
      sceneRef: '',
      characters: [],
      description: '',
      dialogue: '',
      soundEffects: [],
      music: '',
      notes: '',
    };
    setEditingShot(newShot);
    setIsModalOpen(true);
  };

  const handleEditShot = (shot: Shot) => {
    setEditingShot(shot);
    setIsModalOpen(true);
  };

  const handleDeleteShot = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个分镜头吗？',
      onOk: () => {
        const updatedShots = currentShots.filter(shot => shot.id !== id);
        updateEpisodeShots(updatedShots);
        message.success('分镜头已删除');
      },
    });
  };

  const handleSaveShot = (values: any) => {
    if (editingShot) {
      const updatedShot = { ...editingShot, ...values };
      const updatedShots = currentShots.map(shot =>
        shot.id === updatedShot.id ? updatedShot : shot
      );

      if (!editingShot.id) {
        updatedShots.push(updatedShot);
      }

      updateEpisodeShots(updatedShots);
      setIsModalOpen(false);
      setEditingShot(null);
    }
  };

  // 更新当前集数的分镜头
  const updateEpisodeShots = (shots: Shot[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, shots } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  // 计算总时长
  const totalDuration = currentShots.reduce((total, shot) => total + shot.duration, 0);
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  const renderShotsList = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4}>分镜头列表</Title>
          <Text type="secondary">总时长：{formatDuration(totalDuration)}，共 {currentShots.length} 个镜头</Text>
        </div>
        <Space>
          <Button icon={<EyeOutlined />}>预览分镜</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddShot}>
            添加分镜头
          </Button>
        </Space>
      </div>

      <List
        dataSource={currentShots}
        renderItem={(shot) => (
          <Card
            key={shot.id}
            style={{ marginBottom: 16 }}
            actions={[
              <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditShot(shot)}>
                编辑
              </Button>,
              <Button key="preview" type="link" icon={<EyeOutlined />}>
                预览
              </Button>,
              <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteShot(shot.id)}>
                删除
              </Button>,
            ]}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <Tag color="blue" style={{ fontSize: 16, padding: '4px 12px' }}>
                    镜头 {shot.number}
                  </Tag>
                  <Space size={[8, 8]} style={{ marginLeft: 12 }}>
                    <Tag icon={<CameraOutlined />} color="purple">{shot.shotType}</Tag>
                    <Tag icon={<ClockCircleOutlined />} color="green">{shot.duration}秒</Tag>
                    <Tag icon={<VideoCameraOutlined />} color="orange">{shot.cameraAngle}</Tag>
                  </Space>
                </div>

                <div style={{ marginBottom: 12 }}>
                  <Text strong>场景：</Text>
                  <Tag style={{ marginLeft: 8 }}>{shot.sceneRef}</Tag>
                  <Text strong style={{ marginLeft: 16 }}>角色：</Text>
                  {shot.characters.map((char, index) => (
                    <Tag key={index} style={{ marginLeft: 4 }}>{char}</Tag>
                  ))}
                </div>

                <div style={{ margin: '8px 0' }} />

                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>画面描述：</Text>
                      <div style={{ marginTop: 4, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                        {shot.description}
                      </div>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>对白/旁白：</Text>
                      <div style={{ marginTop: 4, padding: 8, background: '#f0f9ff', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
                        {shot.dialogue || '无对白'}
                      </div>
                    </div>
                  </Col>
                  <Col span={12}>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>音效：</Text>
                      <div style={{ marginTop: 4 }}>
                        {shot.soundEffects.length > 0 ? (
                          <Space size={[4, 4]} wrap>
                            {shot.soundEffects.map((effect, index) => (
                              <Tag key={index} icon={<SoundOutlined />}>{effect}</Tag>
                            ))}
                          </Space>
                        ) : (
                          <Text type="secondary">无音效</Text>
                        )}
                      </div>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>背景音乐：</Text>
                      <div style={{ marginTop: 4 }}>
                        {shot.music ? <Tag color="cyan">{shot.music}</Tag> : <Text type="secondary">无背景音乐</Text>}
                      </div>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>备注：</Text>
                      <div style={{ marginTop: 4 }}>
                        {shot.notes || <Text type="secondary">无备注</Text>}
                      </div>
                    </div>
                  </Col>
                </Row>
              </div>
            </div>
          </Card>
        )}
      />
      {currentShots.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <CameraOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无分镜头，点击"添加分镜头"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  const renderTimeline = () => (
    <div style={{ marginTop: 24 }}>
      <Title level={4}>时间线概览</Title>
      <div style={{ padding: 16, background: '#fafafa', borderRadius: 8 }}>
        <div style={{ display: 'flex', overflowX: 'auto', padding: '8px 0' }}>
          {currentShots.map((shot, index) => (
            <div
              key={shot.id}
              style={{
                minWidth: 100,
                marginRight: 8,
                padding: 12,
                background: '#1890ff',
                color: 'white',
                borderRadius: 4,
                position: 'relative',
              }}
            >
              <div style={{ fontWeight: 'bold', fontSize: 16 }}>镜头 {shot.number}</div>
              <div style={{ fontSize: 12, opacity: 0.9 }}>{shot.shotType}</div>
              <div style={{ fontSize: 11, opacity: 0.8 }}>{shot.duration}秒</div>
              <div
                style={{
                  position: 'absolute',
                  top: -20,
                  left: 0,
                  fontSize: 12,
                  color: '#666',
                }}
              >
                {index === 0 ? '00:00' : `${Math.floor(currentShots.slice(0, index).reduce((sum, s) => sum + s.duration, 0) / 60)}:${(currentShots.slice(0, index).reduce((sum, s) => sum + s.duration, 0) % 60).toString().padStart(2, '0')}`}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 20, textAlign: 'center' }}>
          <Text type="secondary">时间线总长度：{formatDuration(totalDuration)}</Text>
        </div>
      </div>
    </div>
  );

  // 渲染集数列表
  const renderEpisodeList = () => (
    <div style={{ borderRight: '1px solid #f0f0f0', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
        <Title level={4} style={{ margin: 0 }}>
          <FolderOpenOutlined style={{ marginRight: 8 }} />
          集数列表
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>共 {episodes.length} 集</Text>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {episodes.map((episode) => (
          <div
            key={episode.id}
            onClick={() => setActiveEpisodeId(episode.id)}
            style={{
              padding: '12px 16px',
              cursor: 'pointer',
              backgroundColor: activeEpisodeId === episode.id ? '#e6f7ff' : 'transparent',
              borderBottom: '1px solid #f0f0f0',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StarOutlined
                  style={{
                    color: activeEpisodeId === episode.id ? '#1890ff' : '#d9d9d9',
                    fontSize: 16
                  }}
                />
                <Text strong style={{ color: activeEpisodeId === episode.id ? '#1890ff' : undefined }}>
                  {episode.title}
                </Text>
              </div>
              <Space size="small">
                <Button
                  type="text"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditEpisode(episode);
                  }}
                />
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  danger
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteEpisode(episode.id);
                  }}
                />
              </Space>
            </div>
            {episode.description && (
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                {episode.description}
              </Text>
            )}
          </div>
        ))}
      </div>

      <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={handleAddEpisode}
        >
          添加新集数
        </Button>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '24px', height: 'calc(100vh - 120px)', display: 'flex' }}>
      {/* 左侧集数列表 */}
      <div style={{ width: 280, marginRight: 24, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        {renderEpisodeList()}
      </div>

      {/* 右侧内容区域 */}
      <div style={{ flex: 1, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Title level={2} style={{ margin: 0 }}>
                <CameraOutlined style={{ marginRight: 12 }} />
                {currentEpisode?.title}
              </Title>
              <Text type="secondary">
                设计和编辑视频的分镜头脚本，包括画面、对白、音效等元素
              </Text>
            </div>
          </div>
        </div>

        <div style={{ padding: '24px', flex: 1 }}>
          {renderShotsList()}
          {renderTimeline()}
        </div>
      </div>

      {/* 分镜头编辑模态框 */}
      <Modal
        title={editingShot?.id ? '编辑分镜头' : '添加分镜头'}
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false);
          setEditingShot(null);
        }}
        footer={null}
        width={800}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveShot}
          initialValues={editingShot || {}}
        >
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="镜头编号"
                name="number"
                rules={[{ required: true, message: '请输入镜头编号' }]}
              >
                <InputNumber min={1} max={100} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="镜头类型"
                name="shotType"
                rules={[{ required: true, message: '请选择镜头类型' }]}
              >
                <Select>
                  <Option value="远景">远景</Option>
                  <Option value="全景">全景</Option>
                  <Option value="中景">中景</Option>
                  <Option value="近景">近景</Option>
                  <Option value="特写">特写</Option>
                  <Option value="大特写">大特写</Option>
                  <Option value="过肩镜头">过肩镜头</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="时长（秒）"
                name="duration"
                rules={[{ required: true, message: '请输入时长' }]}
              >
                <InputNumber min={1} max={60} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="摄像机角度"
                name="cameraAngle"
              >
                <Select>
                  <Option value="正面平视">正面平视</Option>
                  <Option value="俯视">俯视</Option>
                  <Option value="仰视">仰视</Option>
                  <Option value="侧面">侧面</Option>
                  <Option value="斜角">斜角</Option>
                  <Option value="跟踪拍摄">跟踪拍摄</Option>
                  <Option value="摇镜头">摇镜头</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="关联场景"
                name="sceneRef"
              >
                <Input placeholder="输入场景名称或选择已有场景" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="出场角色"
            name="characters"
          >
            <Select mode="tags" placeholder="输入角色名称，按回车添加" />
          </Form.Item>

          <Form.Item
            label="画面描述"
            name="description"
            rules={[{ required: true, message: '请输入画面描述' }]}
          >
            <TextArea rows={4} placeholder="详细描述画面内容，包括构图、灯光、色彩等" />
          </Form.Item>

          <Form.Item
            label="对白/旁白"
            name="dialogue"
          >
            <TextArea rows={3} placeholder="输入对白或旁白内容，可分行" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="音效"
                name="soundEffects"
              >
                <Select mode="tags" placeholder="输入音效名称，按回车添加" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="背景音乐"
                name="music"
              >
                <Input placeholder="输入背景音乐名称" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="备注"
            name="notes"
          >
            <TextArea rows={2} placeholder="其他需要说明的事项" />
          </Form.Item>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsModalOpen(false);
                setEditingShot(null);
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
            </Space>
          </div>
        </Form>
      </Modal>

      {/* 集数编辑抽屉 */}
      <Drawer
        title={editingEpisode ? `编辑 ${editingEpisode.title}` : '添加集数'}
        placement="right"
        width={480}
        open={isDrawerOpen}
        onClose={() => {
          setIsDrawerOpen(false);
          setEditingEpisode(null);
        }}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveEpisode}
          initialValues={editingEpisode || {}}
        >
          <Form.Item
            label="集数标题"
            name="title"
            rules={[{ required: true, message: '请输入集数标题' }]}
          >
            <Input placeholder="例如：第一集 - 初次相遇" />
          </Form.Item>
          <Form.Item
            label="集数编号"
            name="number"
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} disabled={!!editingEpisode?.id} />
          </Form.Item>
          <Form.Item
            label="集数描述"
            name="description"
          >
            <TextArea rows={4} placeholder="描述本集的主要内容..." />
          </Form.Item>
          <div style={{ textAlign: 'right', marginTop: 24 }}>
            <Space>
              <Button onClick={() => {
                setIsDrawerOpen(false);
                setEditingEpisode(null);
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
            </Space>
          </div>
        </Form>
      </Drawer>
    </div>
  );
};

export default Storyboard;
