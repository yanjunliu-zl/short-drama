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
  Select,
  message,
  Row,
  Col,
  Slider,
  Switch,
  Progress,
  Divider,
  Timeline,
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
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

// 视频生成任务类型定义
interface VideoTask {
  id: number;
  name: string;
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

const Video: React.FC = () => {
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
      name: '咖啡馆场景视频',
      status: 'completed',
      progress: 100,
      duration: 45,
      resolution: '1920x1080',
      format: 'mp4',
      createdAt: '2026-03-20 10:30',
    },
    {
      id: 2,
      name: '森林场景视频',
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
      name: '实验室场景视频',
      status: 'pending',
      progress: 0,
      duration: 30,
      resolution: '1280x720',
      format: 'mp4',
      createdAt: '2026-03-20 11:45',
    },
  ]);

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
          const newTask: VideoTask = {
            id: videoTasks.length + 1,
            name: `生成视频 ${new Date().toLocaleTimeString()}`,
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
                <Divider style={{ margin: '12px 0' }} />
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
        <Timeline>
          <Timeline.Item color="green">
            <Text strong>[10:30:25]</Text> 开始处理分镜脚本
          </Timeline.Item>
          <Timeline.Item color="green">
            <Text strong>[10:31:10]</Text> 加载场景资源: 现代咖啡馆
          </Timeline.Item>
          <Timeline.Item color="green">
            <Text strong>[10:32:45]</Text> 加载角色模型: 李明、张薇
          </Timeline.Item>
          <Timeline.Item color="blue">
            <Text strong>[10:35:20]</Text> 开始渲染镜头 1 (远景)
          </Timeline.Item>
          <Timeline.Item color="blue">
            <Text strong>[10:37:50]</Text> 渲染镜头 1 完成
          </Timeline.Item>
          <Timeline.Item color="blue">
            <Text strong>[10:38:15]</Text> 开始渲染镜头 2 (中景)
          </Timeline.Item>
          <Timeline.Item color="blue">
            <Text strong>[10:40:30]</Text> 渲染镜头 2 完成
          </Timeline.Item>
          <Timeline.Item color="blue">
            <Text strong>[10:42:10]</Text> 正在渲染镜头 3 (近景)...
          </Timeline.Item>
          <Timeline.Item color="gray">
            <Text strong>[当前]</Text> 合成音频轨道
          </Timeline.Item>
        </Timeline>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <VideoCameraOutlined style={{ marginRight: 12 }} />
          分镜视频
        </Title>
        <Text type="secondary">将分镜脚本生成为视频，支持预览、生成和下载</Text>
      </div>

      <Card>
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
      </Card>

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
                  <Option value="1:1">1:1 (��方形)</Option>
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

          <Divider>音频设置</Divider>

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

          <Divider>高级设置</Divider>

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
    </div>
  );
};

export default Video;