import React, { useState } from 'react';
import {
  Card,
  Typography,
  Button,
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
  Slider,
  Switch,
  Progress,
  Drawer,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  VideoCameraOutlined,
  SettingOutlined,
  DownloadOutlined,
  EyeOutlined,
  CloudUploadOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  FolderOpenOutlined,
  StarOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

// 视频生成任务类型定义
interface VideoTask {
  id: number;
  name: string;
  episodeId: string;
  episodeTitle: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  duration: number; // 秒
  resolution: string;
  format: string;
  createdAt: string;
  estimatedCompletion?: string;
}

// 视频设置类型定义
interface VideoSettings {
  resolution: string;
  frameRate: number;
  aspectRatio: string;
  format: string;
  quality: number;
  enableSubtitles: boolean;
  enableWatermark: boolean;
  watermarkText: string;
  enableAudio: boolean;
  audioVolume: number;
  outputPath: string;
}

// 集数类型定义
interface Episode {
  id: string;
  title: string;
  number: number;
  description?: string;
}

const Video: React.FC = () => {
  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([
    {
      id: 'ep-1',
      title: '第一集',
      number: 1,
      description: '故事的开端，主角相遇',
    },
    {
      id: 'ep-2',
      title: '第二集',
      number: 2,
      description: '误会加深，情节转折',
    },
  ]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('preview');
  const [videoSettings, setVideoSettings] = useState<VideoSettings>({
    resolution: '1920x1080',
    frameRate: 30,
    aspectRatio: '16:9',
    format: 'mp4',
    quality: 85,
    enableSubtitles: true,
    enableWatermark: false,
    watermarkText: 'TopSeeker',
    enableAudio: true,
    audioVolume: 80,
    outputPath: '/videos/output.mp4',
  });

  const [videoTasks, setVideoTasks] = useState<VideoTask[]>([
    {
      id: 1,
      name: '第一集 - 咖啡馆场景视频',
      episodeId: 'ep-1',
      episodeTitle: '第一集',
      status: 'completed',
      progress: 100,
      duration: 45,
      resolution: '1920x1080',
      format: 'mp4',
      createdAt: '2026-03-20 10:30',
    },
    {
      id: 2,
      name: '第一集 - 森林场景视频',
      episodeId: 'ep-1',
      episodeTitle: '第一集',
      status: 'processing',
      progress: 65,
      duration: 60,
      resolution: '1920x1080',
      format: 'mp4',
      createdAt: '2026-03-20 11:15',
      estimatedCompletion: '2026-03-20 12:00',
    },
    {
      id: 3,
      name: '第二集 - 实验室场景视频',
      episodeId: 'ep-2',
      episodeTitle: '第二集',
      status: 'pending',
      progress: 0,
      duration: 30,
      resolution: '1280x720',
      format: 'mp4',
      createdAt: '2026-03-20 11:45',
    },
  ]);

  // 集数操作
  const handleAddEpisode = () => {
    const newEpisode: Episode = {
      id: `ep-${Date.now()}`,
      title: `第${episodes.length + 1}集`,
      number: episodes.length + 1,
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

  const handleStartGeneration = () => {
    setIsGenerating(true);
    setGenerationProgress(0);

    // 模拟视频生成过程
    const interval = setInterval(() => {
      setGenerationProgress((prev) => {
        const newProgress = prev + 2;
        if (newProgress >= 100) {
          clearInterval(interval);
          setIsGenerating(false);
          message.success('视频生成完成！');

          // 添加新任务到列表
          const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);
          const newTask: VideoTask = {
            id: videoTasks.length + 1,
            name: `${currentEpisode?.title || '集数'} - 生成视频 ${new Date().toLocaleTimeString()}`,
            episodeId: activeEpisodeId,
            episodeTitle: currentEpisode?.title || '未知集数',
            status: 'completed',
            progress: 100,
            duration: 120,
            resolution: videoSettings.resolution,
            format: videoSettings.format,
            createdAt: new Date().toLocaleString(),
          };
          setVideoTasks([newTask, ...videoTasks]);
          return 100;
        }
        return newProgress;
      });
    }, 200);
  };

  const handlePauseGeneration = () => {
    setIsGenerating(false);
    message.info('视频生成已暂停');
  };

  const handleSettingsSave = (values: any) => {
    setVideoSettings({ ...videoSettings, ...values });
    setIsSettingsModalOpen(false);
    message.success('设置已保存');
  };

  const renderVideoPreview = () => (
    <div>
      <Title level={4}>视频预览</Title>
      <div style={{
        width: '100%',
        height: 400,
        backgroundColor: '#000',
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        marginBottom: 16,
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{ textAlign: 'center' }}>
          <VideoCameraOutlined style={{ fontSize: 64, marginBottom: 16 }} />
          <div style={{ fontSize: 18, marginBottom: 8 }}>视频预览区域</div>
          <Text type="secondary">基于分镜脚本生成的视频将在此显示</Text>
        </div>

        {/* 模拟进度条 */}
        {isGenerating && (
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: 4,
            background: 'linear-gradient(90deg, #1890ff, #52c41a)',
            width: `${generationProgress}%`,
          }} />
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginBottom: 24 }}>
        <Button
          type="primary"
          size="large"
          icon={isGenerating ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={isGenerating ? handlePauseGeneration : handleStartGeneration}
          loading={isGenerating}
        >
          {isGenerating ? '暂停生成' : '开始生成视频'}
        </Button>
        <Button
          size="large"
          icon={<SettingOutlined />}
          onClick={() => setIsSettingsModalOpen(true)}
        >
          视频设置
        </Button>
        <Button
          size="large"
          icon={<DownloadOutlined />}
          disabled={!videoTasks.some(task => task.status === 'completed')}
        >
          下载视频
        </Button>
      </div>

      {isGenerating && (
        <div style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text>生成进度</Text>
            <Text strong>{generationProgress}%</Text>
          </div>
          <Progress percent={generationProgress} status="active" />
          <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
            正在渲染视频，请稍候...
          </Text>
        </div>
      )}
    </div>
  );

  const renderTasks = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>生成任务</Title>
        <Button icon={<ReloadOutlined />} onClick={() => message.info('已刷新任务列表')}>
          刷新
        </Button>
      </div>

      <div style={{ maxHeight: 500, overflowY: 'auto' }}>
        {videoTasks.map((task) => (
          <Card
            key={task.id}
            style={{ marginBottom: 12 }}
            size="small"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <Text strong style={{ marginRight: 12 }}>{task.name}</Text>
                  <Tag color={
                    task.status === 'completed' ? 'success' :
                    task.status === 'processing' ? 'processing' :
                    task.status === 'failed' ? 'error' : 'default'
                  }>
                    {task.status === 'completed' ? '已完成' :
                     task.status === 'processing' ? '处理中' :
                     task.status === 'failed' ? '失败' : '等待中'}
                  </Tag>
                  <Tag color="blue" style={{ marginLeft: 8 }}>{task.episodeTitle}</Tag>
                </div>

                <div style={{ display: 'flex', gap: 24, marginBottom: 8 }}>
                  <div>
                    <Text type="secondary">时长: </Text>
                    <Text>{task.duration}秒</Text>
                  </div>
                  <div>
                    <Text type="secondary">分辨率: </Text>
                    <Text>{task.resolution}</Text>
                  </div>
                  <div>
                    <Text type="secondary">格式: </Text>
                    <Text>{task.format.toUpperCase()}</Text>
                  </div>
                </div>

                <div>
                  <Text type="secondary">创建时间: </Text>
                  <Text>{task.createdAt}</Text>
                </div>

                {task.estimatedCompletion && (
                  <div>
                    <Text type="secondary">预计完成: </Text>
                    <Text>{task.estimatedCompletion}</Text>
                  </div>
                )}
              </div>

              <div style={{ textAlign: 'center', minWidth: 100 }}>
                {task.status === 'processing' ? (
                  <>
                    <Progress
                      type="circle"
                      percent={task.progress}
                      size={60}
                      status="active"
                    />
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary">处理中...</Text>
                    </div>
                  </>
                ) : task.status === 'completed' ? (
                  <>
                    <CheckCircleOutlined style={{ fontSize: 32, color: '#52c41a' }} />
                    <div style={{ marginTop: 8 }}>
                      <Button type="link" icon={<EyeOutlined />} size="small">预览</Button>
                      <Button type="link" icon={<DownloadOutlined />} size="small">下载</Button>
                    </div>
                  </>
                ) : (
                  <Progress
                    type="circle"
                    percent={task.progress}
                    size={60}
                    status="normal"
                  />
                )}
              </div>
            </div>

            {task.status === 'processing' && (
              <>
                <div style={{ margin: '12px 0' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <Text type="secondary">当前进度: {task.progress}%</Text>
                  </div>
                  <div>
                    <Progress
                      percent={task.progress}
                      status="active"
                      style={{ width: 200 }}
                    />
                  </div>
                </div>
              </>
            )}
          </Card>
        ))}
      </div>
    </div>
  );

  const renderGenerationLog = () => (
    <div>
      <Title level={4}>生成日志</Title>
      <div style={{
        backgroundColor: '#f5f5f5',
        borderRadius: 8,
        padding: 16,
        height: 300,
        overflowY: 'auto',
        fontFamily: 'monospace',
        fontSize: 12,
      }}>
        <div style={{ marginBottom: 16 }}>
          <Text strong>当前集数：</Text>
          <Tag color="blue">{episodes.find(ep => ep.id === activeEpisodeId)?.title}</Tag>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Text strong>生成任务列表：</Text>
        </div>
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          <li style={{ marginBottom: 8, color: '#52c41a' }}>
            <Text strong>[10:30:25]</Text> 开始处理分镜脚本 - {episodes.find(ep => ep.id === activeEpisodeId)?.title}
          </li>
          <li style={{ marginBottom: 8, color: '#52c41a' }}>
            <Text strong>[10:31:10]</Text> 加载场景资源: 现代咖啡馆
          </li>
          <li style={{ marginBottom: 8, color: '#52c41a' }}>
            <Text strong>[10:32:45]</Text> 加载角色模型: 李明、张薇
          </li>
          <li style={{ marginBottom: 8, color: '#1890ff' }}>
            <Text strong>[10:35:20]</Text> 开始渲染镜头 1 (远景)
          </li>
          <li style={{ marginBottom: 8, color: '#1890ff' }}>
            <Text strong>[10:37:50]</Text> 渲染镜头 1 完成
          </li>
          <li style={{ marginBottom: 8, color: '#1890ff' }}>
            <Text strong>[10:38:15]</Text> 开始渲染镜头 2 (中景)
          </li>
          <li style={{ marginBottom: 8, color: '#1890ff' }}>
            <Text strong>[10:40:30]</Text> 渲染镜头 2 完成
          </li>
          <li style={{ marginBottom: 8, color: '#1890ff' }}>
            <Text strong>[10:42:10]</Text> 正在渲染镜头 3 (近景)...
          </li>
          <li style={{ color: '#999' }}>
            <Text strong>[当前]</Text> 合成音频轨道
          </li>
        </ul>
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
                <VideoCameraOutlined style={{ marginRight: 12 }} />
                {episodes.find(ep => ep.id === activeEpisodeId)?.title}
              </Title>
              <Text type="secondary">
                将分镜脚本生成为视频，支持预览、生成和下载
              </Text>
            </div>
          </div>
        </div>

        <div style={{ padding: '24px', flex: 1 }}>
          <div style={{ marginBottom: 24 }}>
            <Space>
              <Button
                type={activeTab === 'preview' ? 'primary' : 'default'}
                icon={<PlayCircleOutlined />}
                onClick={() => setActiveTab('preview')}
              >
                视频预览
              </Button>
              <Button
                type={activeTab === 'tasks' ? 'primary' : 'default'}
                icon={<CloudUploadOutlined />}
                onClick={() => setActiveTab('tasks')}
              >
                生成任务
              </Button>
              <Button
                type={activeTab === 'log' ? 'primary' : 'default'}
                icon={<EyeOutlined />}
                onClick={() => setActiveTab('log')}
              >
                生成日志
              </Button>
            </Space>
          </div>

          <div style={{ marginTop: 24 }}>
            {activeTab === 'preview' && renderVideoPreview()}
            {activeTab === 'tasks' && renderTasks()}
            {activeTab === 'log' && renderGenerationLog()}
          </div>
        </div>
      </div>

      {/* 视频设置模态框 */}
      <Modal
        title="视频设置"
        open={isSettingsModalOpen}
        onCancel={() => setIsSettingsModalOpen(false)}
        footer={null}
        width={700}
      >
        <Form
          layout="vertical"
          onFinish={handleSettingsSave}
          initialValues={videoSettings}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="分辨率"
                name="resolution"
                rules={[{ required: true, message: '请选择分辨率' }]}
              >
                <Select>
                  <Option value="3840x2160">4K (3840x2160)</Option>
                  <Option value="2560x1440">2K (2560x1440)</Option>
                  <Option value="1920x1080">全高清 (1920x1080)</Option>
                  <Option value="1280x720">高清 (1280x720)</Option>
                  <Option value="854x480">标清 (854x480)</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="帧率 (FPS)"
                name="frameRate"
                rules={[{ required: true, message: '请选择帧率' }]}
              >
                <Select>
                  <Option value={60}>60 FPS</Option>
                  <Option value={30}>30 FPS</Option>
                  <Option value={25}>25 FPS</Option>
                  <Option value={24}>24 FPS</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="画面比例"
                name="aspectRatio"
              >
                <Select>
                  <Option value="16:9">16:9 (宽屏)</Option>
                  <Option value="4:3">4:3 (标准)</Option>
                  <Option value="1:1">1:1 (正方形)</Option>
                  <Option value="21:9">21:9 (超宽屏)</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="输出格式"
                name="format"
              >
                <Select>
                  <Option value="mp4">MP4</Option>
                  <Option value="mov">MOV</Option>
                  <Option value="avi">AVI</Option>
                  <Option value="webm">WebM</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="视频质量"
            name="quality"
          >
            <Slider
              min={1}
              max={100}
              marks={{
                1: '最低',
                25: '低',
                50: '中',
                75: '高',
                100: '最高',
              }}
            />
          </Form.Item>

          <div style={{ margin: '16px 0' }} />

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="启用音频"
                name="enableAudio"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="音频音量"
                name="audioVolume"
              >
                <Slider min={0} max={100} />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ margin: '16px 0' }} />

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="启用字幕"
                name="enableSubtitles"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="启用水印"
                name="enableWatermark"
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="水印文本"
            name="watermarkText"
            dependencies={['enableWatermark']}
          >
            {({ getFieldValue }) =>
              getFieldValue('enableWatermark') ? (
                <Input placeholder="输入水印文本" />
              ) : (
                <Text type="secondary">水印已禁用</Text>
              )
            }
          </Form.Item>

          <Form.Item
            label="输出路径"
            name="outputPath"
          >
            <Input placeholder="/path/to/output/video.mp4" />
          </Form.Item>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsSettingsModalOpen(false)}>
                取消
              </Button>
              <Button type="primary" htmlType="submit">
                保存设置
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

export default Video;
