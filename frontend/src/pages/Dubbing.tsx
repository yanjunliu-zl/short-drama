import React, { useState, useRef } from 'react';
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
  Divider,
  Upload,
  Tooltip,
} from 'antd';
import {
  SoundOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  UploadOutlined,
  EditOutlined,
  DeleteOutlined,
  DownloadOutlined,
  SettingOutlined,
  SyncOutlined,
  RobotOutlined,
  UserOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

// 配音任务类型定义
interface DubbingTask {
  id: number;
  name: string;
  character: string;
  voiceType: string;
  duration: number; // 秒
  syncStatus: 'perfect' | 'good' | 'fair' | 'poor';
  audioQuality: number; // 1-100
  lipSyncScore: number; // 1-100
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
}

// 音频片段类型定义
interface AudioClip {
  id: number;
  startTime: number; // 秒
  endTime: number; // 秒
  text: string;
  character: string;
  emotion: string;
  volume: number;
  pitch: number;
  speed: number;
  audioUrl?: string;
}

const Dubbing: React.FC = () => {
  const [activeTab, setActiveTab] = useState('editor');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration] = useState(120); // 总时长120秒
  const [audioClips, setAudioClips] = useState<AudioClip[]>([
    {
      id: 1,
      startTime: 0,
      endTime: 5,
      text: '你好，我能坐这里吗？',
      character: '李明',
      emotion: '礼貌',
      volume: 80,
      pitch: 50,
      speed: 100,
    },
    {
      id: 2,
      startTime: 6,
      endTime: 12,
      text: '当然可以，请坐。你也喜欢这本书吗？',
      character: '张薇',
      emotion: '友好',
      volume: 75,
      pitch: 60,
      speed: 95,
    },
    {
      id: 3,
      startTime: 13,
      endTime: 20,
      text: '是的，我一直很喜欢这位作者的作品。',
      character: '李明',
      emotion: '热情',
      volume: 85,
      pitch: 55,
      speed: 105,
    },
  ]);

  const [dubbingTasks, _setDubbingTasks] = useState<DubbingTask[]>([
    {
      id: 1,
      name: '李明配音',
      character: '李明',
      voiceType: '青年男声',
      duration: 45,
      syncStatus: 'good',
      audioQuality: 88,
      lipSyncScore: 85,
      status: 'completed',
      progress: 100,
    },
    {
      id: 2,
      name: '张薇配音',
      character: '张薇',
      voiceType: '青年女声',
      duration: 38,
      syncStatus: 'perfect',
      audioQuality: 92,
      lipSyncScore: 90,
      status: 'completed',
      progress: 100,
    },
    {
      id: 3,
      name: '王强配音',
      character: '王强',
      voiceType: '中年男声',
      duration: 25,
      syncStatus: 'fair',
      audioQuality: 78,
      lipSyncScore: 72,
      status: 'processing',
      progress: 65,
    },
  ]);

  const [editingClip, setEditingClip] = useState<AudioClip | null>(null);
  const [isClipModalOpen, setIsClipModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  // 模拟播放器功能
  const playTimerRef = useRef<NodeJS.Timeout | null>(null);

  const handlePlay = () => {
    setIsPlaying(true);
    playTimerRef.current = setInterval(() => {
      setCurrentTime((prev) => {
        if (prev >= totalDuration) {
          if (playTimerRef.current) clearInterval(playTimerRef.current);
          setIsPlaying(false);
          return totalDuration;
        }
        return prev + 0.5;
      });
    }, 500);
  };

  const handlePause = () => {
    setIsPlaying(false);
    if (playTimerRef.current) {
      clearInterval(playTimerRef.current);
      playTimerRef.current = null;
    }
  };

  const handleTimeChange = (value: number) => {
    setCurrentTime(value);
  };

  // 音频片段操作
  const handleAddClip = () => {
    const newClip: AudioClip = {
      id: audioClips.length + 1,
      startTime: 0,
      endTime: 5,
      text: '',
      character: '',
      emotion: '中性',
      volume: 75,
      pitch: 50,
      speed: 100,
    };
    setEditingClip(newClip);
    setIsClipModalOpen(true);
  };

  const handleEditClip = (clip: AudioClip) => {
    setEditingClip(clip);
    setIsClipModalOpen(true);
  };

  const handleDeleteClip = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个音频片段吗？',
      onOk: () => {
        setAudioClips(audioClips.filter(clip => clip.id !== id));
        message.success('音频片段已删除');
      },
    });
  };

  const handleSaveClip = (values: any) => {
    if (editingClip) {
      const updatedClip = { ...editingClip, ...values };
      if (editingClip.id) {
        setAudioClips(audioClips.map(clip =>
          clip.id === editingClip.id ? updatedClip : clip
        ));
        message.success('音频片段已更新');
      } else {
        setAudioClips([...audioClips, updatedClip]);
        message.success('音频片段已添加');
      }
      setIsClipModalOpen(false);
      setEditingClip(null);
    }
  };

  const handleStartDubbing = () => {
    message.info('开始对口型处理...');
    // 模拟处理过程
    setTimeout(() => {
      message.success('对口型处理完成！');
    }, 2000);
  };

  const renderTimelineEditor = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>时间轴编辑器</Title>
        <Space>
          <Button icon={<SettingOutlined />} onClick={() => setIsSettingsModalOpen(true)}>
            音频设置
          </Button>
          <Button type="primary" icon={<SyncOutlined />} onClick={handleStartDubbing}>
            开始对口型
          </Button>
        </Space>
      </div>

      {/* 播放器控制 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Button
            type="text"
            icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={isPlaying ? handlePause : handlePlay}
            style={{ fontSize: 24 }}
          />
          <div style={{ flex: 1 }}>
            <Slider
              min={0}
              max={totalDuration}
              value={currentTime}
              onChange={handleTimeChange}
              tooltip={{ formatter: (value) => `${Math.floor(value! / 60)}:${(value! % 60).toString().padStart(2, '0')}` }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <Text type="secondary">{Math.floor(currentTime / 60)}:{(currentTime % 60).toString().padStart(2, '0')}</Text>
              <Text type="secondary">{Math.floor(totalDuration / 60)}:{(totalDuration % 60).toString().padStart(2, '0')}</Text>
            </div>
          </div>
          <Tag color="blue">总时长: {totalDuration}秒</Tag>
        </div>
      </Card>

      {/* 时间轴 */}
      <div style={{
        height: 200,
        backgroundColor: '#f5f5f5',
        borderRadius: 8,
        padding: 16,
        marginBottom: 16,
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* 时间刻度 */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 20,
          borderBottom: '1px solid #ddd',
          display: 'flex',
        }}>
          {Array.from({ length: totalDuration / 10 + 1 }).map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                borderRight: '1px solid #ddd',
                textAlign: 'center',
                fontSize: 10,
                color: '#666',
                lineHeight: '20px',
              }}
            >
              {i * 10}s
            </div>
          ))}
        </div>

        {/* 音频片段条 */}
        <div style={{ marginTop: 30 }}>
          {audioClips.map((clip) => {
            const left = (clip.startTime / totalDuration) * 100;
            const width = ((clip.endTime - clip.startTime) / totalDuration) * 100;
            const isActive = currentTime >= clip.startTime && currentTime <= clip.endTime;

            return (
              <Tooltip key={clip.id} title={`${clip.character}: ${clip.text}`}>
                <div
                  style={{
                    position: 'absolute',
                    left: `${left}%`,
                    width: `${width}%`,
                    height: 40,
                    backgroundColor: isActive ? '#1890ff' : '#52c41a',
                    borderRadius: 4,
                    marginTop: 8,
                    padding: 8,
                    cursor: 'pointer',
                    border: isActive ? '2px solid #096dd9' : '1px solid #389e0d',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                  onClick={() => handleEditClip(clip)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <UserOutlined />
                    <Text style={{ color: 'white', fontSize: 12 }}>{clip.character}</Text>
                  </div>
                  <div style={{ fontSize: 10, opacity: 0.9 }}>{clip.emotion}</div>
                </div>
              </Tooltip>
            );
          })}
        </div>

        {/* 播放指针 */}
        <div
          style={{
            position: 'absolute',
            left: `${(currentTime / totalDuration) * 100}%`,
            top: 20,
            bottom: 0,
            width: 2,
            backgroundColor: '#f5222d',
            zIndex: 10,
          }}
        />
      </div>

      {/* 音频片段列表 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <Text strong>音频片段列表</Text>
          <Button type="primary" size="small" icon={<SoundOutlined />} onClick={handleAddClip}>
            添加片段
          </Button>
        </div>

        {audioClips.map((clip) => (
          <Card
            key={clip.id}
            size="small"
            style={{ marginBottom: 8 }}
            actions={[
              <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditClip(clip)}>
                编辑
              </Button>,
              <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteClip(clip.id)}>
                删除
              </Button>,
            ]}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <Tag color="blue">{clip.character}</Tag>
                  <Tag color="green">{clip.emotion}</Tag>
                  <Tag color="purple">{clip.startTime}s - {clip.endTime}s</Tag>
                </div>
                <Text style={{ display: 'block', marginBottom: 8 }}>{clip.text}</Text>
                <div style={{ display: 'flex', gap: 16 }}>
                  <div><Text type="secondary">音量: </Text>{clip.volume}%</div>
                  <div><Text type="secondary">音调: </Text>{clip.pitch}%</div>
                  <div><Text type="secondary">语速: </Text>{clip.speed}%</div>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderTasks = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>配音任务</Title>
        <Upload>
          <Button icon={<UploadOutlined />}>上传音频</Button>
        </Upload>
      </div>

      <Row gutter={[16, 16]}>
        {dubbingTasks.map((task) => (
          <Col xs={24} sm={12} lg={8} key={task.id}>
            <Card
              actions={[
                <Button key="preview" type="link" icon={<PlayCircleOutlined />}>
                  预览
                </Button>,
                <Button key="download" type="link" icon={<DownloadOutlined />}>
                  下载
                </Button>,
                <Button key="edit" type="link" icon={<EditOutlined />}>
                  编辑
                </Button>,
              ]}
            >
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text strong>{task.name}</Text>
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
              </div>

              <div style={{ marginBottom: 12 }}>
                <div><Text type="secondary">角色: </Text>{task.character}</div>
                <div><Text type="secondary">声音类型: </Text>{task.voiceType}</div>
                <div><Text type="secondary">时长: </Text>{task.duration}秒</div>
              </div>

              <Divider style={{ margin: '12px 0' }} />

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text type="secondary">对口型评分</Text>
                  <Text strong style={{ color: task.lipSyncScore >= 80 ? '#52c41a' : task.lipSyncScore >= 60 ? '#faad14' : '#f5222d' }}>
                    {task.lipSyncScore}/100
                  </Text>
                </div>
                <Progress
                  percent={task.lipSyncScore}
                  status="normal"
                  strokeColor={task.lipSyncScore >= 80 ? '#52c41a' : task.lipSyncScore >= 60 ? '#faad14' : '#f5222d'}
                />
              </div>

              <div style={{ marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <Text type="secondary">音频质量</Text>
                  <Text strong>{task.audioQuality}/100</Text>
                </div>
                <Progress percent={task.audioQuality} status="normal" />
              </div>

              <div style={{ marginTop: 12 }}>
                <Text type="secondary">同步状态: </Text>
                <Tag color={
                  task.syncStatus === 'perfect' ? 'success' :
                  task.syncStatus === 'good' ? 'processing' :
                  task.syncStatus === 'fair' ? 'warning' : 'error'
                }>
                  {task.syncStatus === 'perfect' ? '完美' :
                   task.syncStatus === 'good' ? '良好' :
                   task.syncStatus === 'fair' ? '一般' : '较差'}
                </Tag>
              </div>

              {task.status === 'processing' && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Text type="secondary">处理进度</Text>
                    <Text strong>{task.progress}%</Text>
                  </div>
                  <Progress percent={task.progress} status="active" />
                </div>
              )}
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  const renderVoiceSettings = () => (
    <div>
      <Title level={4}>语音合成设置</Title>
      <Card>
        <Form layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="默认声音类型">
                <Select defaultValue="青年男声">
                  <Option value="青年男声">青年男声</Option>
                  <Option value="青年女声">青年女声</Option>
                  <Option value="中年男声">中年男声</Option>
                  <Option value="中年女声">中年女声</Option>
                  <Option value="老年男声">老年男声</Option>
                  <Option value="老年女声">老年女声</Option>
                  <Option value="童声">童声</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="语速调整">
                <Slider min={50} max={150} defaultValue={100} marks={{ 50: '慢', 100: '正常', 150: '快' }} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="音调调整">
                <Slider min={30} max={70} defaultValue={50} marks={{ 30: '低', 50: '中', 70: '高' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="音量调整">
                <Slider min={0} max={100} defaultValue={75} marks={{ 0: '静音', 50: '适中', 100: '最大' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="情感模式">
            <Select mode="multiple" defaultValue={['中性']}>
              <Option value="中性">中性</Option>
              <Option value="高兴">高兴</Option>
              <Option value="悲伤">悲伤</Option>
              <Option value="愤怒">愤怒</Option>
              <Option value="惊讶">惊讶</Option>
              <Option value="恐惧">恐惧</Option>
            </Select>
          </Form.Item>

          <Form.Item label="自动对口型" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>

          <Form.Item label="音频格式">
            <Select defaultValue="mp3">
              <Option value="mp3">MP3</Option>
              <Option value="wav">WAV</Option>
              <Option value="ogg">OGG</Option>
              <Option value="aac">AAC</Option>
            </Select>
          </Form.Item>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button>重置</Button>
              <Button type="primary">保存设置</Button>
            </Space>
          </div>
        </Form>
      </Card>
    </div>
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <SoundOutlined style={{ marginRight: 12 }} />
          配音对口型
        </Title>
        <Text type="secondary">管理配音音频，调整对口型同步，配置语音合成参数</Text>
      </div>

      <Card>
        <div style={{ marginBottom: 24 }}>
          <Space>
            <Button
              type={activeTab === 'editor' ? 'primary' : 'default'}
              icon={<EditOutlined />}
              onClick={() => setActiveTab('editor')}
            >
              时间轴编辑器
            </Button>
            <Button
              type={activeTab === 'tasks' ? 'primary' : 'default'}
              icon={<SoundOutlined />}
              onClick={() => setActiveTab('tasks')}
            >
              配音任务
            </Button>
            <Button
              type={activeTab === 'voice' ? 'primary' : 'default'}
              icon={<RobotOutlined />}
              onClick={() => setActiveTab('voice')}
            >
              语音合成
            </Button>
          </Space>
        </div>

        <div style={{ marginTop: 24 }}>
          {activeTab === 'editor' && renderTimelineEditor()}
          {activeTab === 'tasks' && renderTasks()}
          {activeTab === 'voice' && renderVoiceSettings()}
        </div>
      </Card>

      {/* 音频片段编辑模态框 */}
      <Modal
        title={editingClip?.id ? '编辑音频片段' : '添加音频片段'}
        open={isClipModalOpen}
        onCancel={() => {
          setIsClipModalOpen(false);
          setEditingClip(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveClip}
          initialValues={editingClip || {}}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="开始时间（秒）"
                name="startTime"
                rules={[{ required: true, message: '请输入开始时间' }]}
              >
                <InputNumber min={0} max={totalDuration} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="结束时间（秒）"
                name="endTime"
                rules={[{ required: true, message: '请输入结束时间' }]}
              >
                <InputNumber min={0} max={totalDuration} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="角色"
            name="character"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="例如：李明" />
          </Form.Item>

          <Form.Item
            label="文本内容"
            name="text"
            rules={[{ required: true, message: '请输入文本内容' }]}
          >
            <Input.TextArea rows={3} placeholder="输入对白文本" />
          </Form.Item>

          <Form.Item
            label="情感"
            name="emotion"
          >
            <Select>
              <Option value="中性">中性</Option>
              <Option value="高兴">高兴</Option>
              <Option value="悲伤">悲伤</Option>
              <Option value="愤怒">愤怒</Option>
              <Option value="惊讶">惊讶</Option>
              <Option value="恐惧">恐惧</Option>
              <Option value="兴奋">兴奋</Option>
              <Option value="平静">平静</Option>
            </Select>
          </Form.Item>

          <Divider>音频参数</Divider>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="音量 (%)"
                name="volume"
              >
                <Slider min={0} max={100} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="音调 (%)"
                name="pitch"
              >
                <Slider min={30} max={70} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="语速 (%)"
                name="speed"
              >
                <Slider min={50} max={150} />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsClipModalOpen(false);
                setEditingClip(null);
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

      {/* 音频设置模态框 */}
      <Modal
        title="音频设置"
        open={isSettingsModalOpen}
        onCancel={() => setIsSettingsModalOpen(false)}
        footer={null}
        width={500}
      >
        <Form layout="vertical">
          <Form.Item label="采样率">
            <Select defaultValue="44100">
              <Option value="44100">44.1 kHz (CD质量)</Option>
              <Option value="48000">48 kHz (专业音频)</Option>
              <Option value="22050">22.05 kHz (广播质量)</Option>
              <Option value="16000">16 kHz (语音质量)</Option>
            </Select>
          </Form.Item>

          <Form.Item label="位深度">
            <Select defaultValue="16">
              <Option value="16">16-bit</Option>
              <Option value="24">24-bit</Option>
              <Option value="32">32-bit</Option>
            </Select>
          </Form.Item>

          <Form.Item label="声道">
            <Select defaultValue="stereo">
              <Option value="mono">单声道</Option>
              <Option value="stereo">立体声</Option>
              <Option value="5.1">5.1环绕声</Option>
            </Select>
          </Form.Item>

          <Form.Item label="降噪处理" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>

          <Form.Item label="音频归一化" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsSettingsModalOpen(false)}>
                取消
              </Button>
              <Button type="primary" onClick={() => {
                setIsSettingsModalOpen(false);
                message.success('音频设置已保存');
              }}>
                保存设置
              </Button>
            </Space>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default Dubbing;