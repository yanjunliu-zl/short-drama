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
  Select,
  message,
  Row,
  Col,
  Slider,
  Switch,
  Tabs,
  List,
  Avatar,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  EyeOutlined,
  DownloadOutlined,
  SettingOutlined,
  HeartOutlined,
  ShareAltOutlined,
  FullscreenOutlined,
  SoundOutlined,
  MutedOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;
const { TabPane } = Tabs;

// 视频预览类型定义
interface PreviewVideo {
  id: number;
  title: string;
  description: string;
  duration: number; // 秒
  resolution: string;
  format: string;
  thumbnailUrl?: string;
  fileSize: string;
  createdAt: string;
  views: number;
  likes: number;
  quality: string; // 低、中、高、4K
  hasAudio: boolean;
  hasSubtitles: boolean;
  status: 'ready' | 'processing' | 'error';
}

// 播放列表类型定义
interface PlaylistItem {
  id: number;
  title: string;
  duration: number;
  order: number;
  thumbnailUrl?: string;
}

// 播放器状态类型定义
interface PlayerState {
  isPlaying: boolean;
  currentTime: number;
  volume: number;
  isMuted: boolean;
  playbackRate: number;
  isFullscreen: boolean;
  quality: string;
  subtitleLanguage?: string;
}

const Preview: React.FC = () => {
  const [activeTab, setActiveTab] = useState('player');
  const [currentVideo, setCurrentVideo] = useState<PreviewVideo | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState>({
    isPlaying: false,
    currentTime: 0,
    volume: 75,
    isMuted: false,
    playbackRate: 1.0,
    isFullscreen: false,
    quality: 'high',
  });
  const [isQualityModalOpen, setIsQualityModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isPlaylistModalOpen, setIsPlaylistModalOpen] = useState(false);

  const playTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 示例视频数据
  const [previewVideos, setPreviewVideos] = useState<PreviewVideo[]>([
    {
      id: 1,
      title: '咖啡馆对话场景',
      description: '商务男士与学生少女在咖啡馆的对话场景',
      duration: 45,
      resolution: '1920x1080',
      format: 'mp4',
      fileSize: '85.2 MB',
      createdAt: '2026-03-20 10:30',
      views: 156,
      likes: 42,
      quality: 'high',
      hasAudio: true,
      hasSubtitles: true,
      status: 'ready',
    },
    {
      id: 2,
      title: '森林漫步场景',
      description: '清晨森林中的漫步场景，自然光线效果',
      duration: 60,
      resolution: '1920x1080',
      format: 'mp4',
      fileSize: '112.5 MB',
      createdAt: '2026-03-20 11:15',
      views: 89,
      likes: 23,
      quality: 'high',
      hasAudio: true,
      hasSubtitles: false,
      status: 'ready',
    },
    {
      id: 3,
      title: '科技实验室场景',
      description: '未来科技实验室中的特效演示',
      duration: 30,
      resolution: '1280x720',
      format: 'mp4',
      fileSize: '45.8 MB',
      createdAt: '2026-03-20 11:45',
      views: 67,
      likes: 18,
      quality: 'medium',
      hasAudio: true,
      hasSubtitles: true,
      status: 'processing',
    },
  ]);

  // 示例播放列表数据
  const [playlist, _setPlaylist] = useState<PlaylistItem[]>([
    {
      id: 1,
      title: '咖啡馆对话场景',
      duration: 45,
      order: 1,
    },
    {
      id: 2,
      title: '森林漫步场景',
      duration: 60,
      order: 2,
    },
    {
      id: 3,
      title: '科技实验室场景',
      duration: 30,
      order: 3,
    },
    {
      id: 4,
      title: '城市夜景转场',
      duration: 25,
      order: 4,
    },
    {
      id: 5,
      title: '角色特写镜头',
      duration: 15,
      order: 5,
    },
  ]);

  // 初始化当前视频
  React.useEffect(() => {
    if (previewVideos.length > 0 && !currentVideo) {
      setCurrentVideo(previewVideos[0]);
    }
  }, [previewVideos, currentVideo]);

  // 播放器控制函数
  const handlePlay = () => {
    if (!currentVideo) return;

    setPlayerState(prev => ({ ...prev, isPlaying: true }));

    playTimerRef.current = setInterval(() => {
      setPlayerState(prev => {
        if (prev.currentTime >= currentVideo.duration) {
          if (playTimerRef.current) clearInterval(playTimerRef.current);
          return { ...prev, isPlaying: false, currentTime: currentVideo.duration };
        }
        return { ...prev, currentTime: prev.currentTime + 1 };
      });
    }, 1000);
  };

  const handlePause = () => {
    setPlayerState(prev => ({ ...prev, isPlaying: false }));
    if (playTimerRef.current) {
      clearInterval(playTimerRef.current);
      playTimerRef.current = null;
    }
  };

  const handleSeek = (value: number) => {
    setPlayerState(prev => ({ ...prev, currentTime: value }));
  };

  const handleVolumeChange = (value: number) => {
    setPlayerState(prev => ({
      ...prev,
      volume: value,
      isMuted: value === 0
    }));
  };

  const handleToggleMute = () => {
    setPlayerState(prev => ({ ...prev, isMuted: !prev.isMuted }));
  };

  const handlePlaybackRateChange = (rate: number) => {
    setPlayerState(prev => ({ ...prev, playbackRate: rate }));
  };

  const handleQualityChange = (quality: string) => {
    setPlayerState(prev => ({ ...prev, quality }));
    setIsQualityModalOpen(false);
    message.success(`已切换至${quality}画质`);
  };

  const handleSelectVideo = (video: PreviewVideo) => {
    setCurrentVideo(video);
    setPlayerState(prev => ({ ...prev, currentTime: 0, isPlaying: false }));
    if (playTimerRef.current) {
      clearInterval(playTimerRef.current);
      playTimerRef.current = null;
    }
    message.info(`正在加载: ${video.title}`);
  };

  const handleDownload = () => {
    if (!currentVideo) return;
    message.success(`开始下载: ${currentVideo.title}`);
  };

  const handleLike = () => {
    if (!currentVideo) return;
    const updatedVideos = previewVideos.map(video =>
      video.id === currentVideo.id
        ? { ...video, likes: video.likes + 1 }
        : video
    );
    setPreviewVideos(updatedVideos);
    setCurrentVideo(updatedVideos.find(v => v.id === currentVideo.id) || currentVideo);
    message.success('已点赞！');
  };

  const handleShare = () => {
    if (!currentVideo) return;
    message.info(`分享链接已复制到剪贴板: ${currentVideo.title}`);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 渲染视频播放器
  const renderPlayer = () => (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={3}>
            <EyeOutlined style={{ marginRight: 12 }} />
            视频预览
          </Title>
          <Space>
            <Button
              icon={<AppstoreOutlined />}
              onClick={() => setIsPlaylistModalOpen(true)}
            >
              播放列表
            </Button>
            <Button
              icon={<SettingOutlined />}
              onClick={() => setIsSettingsModalOpen(true)}
            >
              播放设置
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              disabled={!currentVideo}
            >
              下载视频
            </Button>
          </Space>
        </div>
        {currentVideo && (
          <Text type="secondary">{currentVideo.description}</Text>
        )}
      </div>

      {/* 视频播放器区域 */}
      <Card style={{ marginBottom: 24, padding: 0, overflow: 'hidden' }}>
        <div style={{
          backgroundColor: '#000',
          height: 480,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
        }}>
          {/* 视频预览区域 */}
          <div style={{ textAlign: 'center', color: 'white' }}>
            <PlayCircleOutlined style={{ fontSize: 64, color: 'rgba(255,255,255,0.8)' }} />
            <div style={{ marginTop: 16, fontSize: 18 }}>
              {currentVideo?.title || '选择视频开始预览'}
            </div>
            {currentVideo && (
              <div style={{ marginTop: 8, color: 'rgba(255,255,255,0.6)' }}>
                分辨率: {currentVideo.resolution} | 时长: {formatTime(currentVideo.duration)}
              </div>
            )}
          </div>

          {/* 播放器控制条 */}
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            background: 'linear-gradient(transparent, rgba(0,0,0,0.8))',
            padding: '20px 24px 16px',
          }}>
            {/* 进度条 */}
            <div style={{ marginBottom: 16 }}>
              <Slider
                min={0}
                max={currentVideo?.duration || 100}
                value={playerState.currentTime}
                onChange={handleSeek}
                tooltip={{ formatter: (value) => formatTime(value || 0) }}
                styles={{
                  track: { background: '#1890ff' },
                  rail: { background: 'rgba(255,255,255,0.2)' },
                }}
              />
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: 8,
                color: 'white'
              }}>
                <Text style={{ color: 'white' }}>{formatTime(playerState.currentTime)}</Text>
                <Text style={{ color: 'white' }}>{formatTime(currentVideo?.duration || 0)}</Text>
              </div>
            </div>

            {/* 控制按钮 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <Space>
                <Button
                  type="text"
                  icon={playerState.isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={playerState.isPlaying ? handlePause : handlePlay}
                  style={{ color: 'white', fontSize: 24 }}
                />
                <Button
                  type="text"
                  icon={<StepBackwardOutlined />}
                  style={{ color: 'white' }}
                />
                <Button
                  type="text"
                  icon={<StepForwardOutlined />}
                  style={{ color: 'white' }}
                />
                <Button
                  type="text"
                  icon={playerState.isMuted ? <MutedOutlined /> : <SoundOutlined />}
                  onClick={handleToggleMute}
                  style={{ color: 'white' }}
                />
                <div style={{ width: 100 }}>
                  <Slider
                    min={0}
                    max={100}
                    value={playerState.isMuted ? 0 : playerState.volume}
                    onChange={handleVolumeChange}
                    styles={{
                      track: { background: '#1890ff' },
                      rail: { background: 'rgba(255,255,255,0.2)' },
                    }}
                  />
                </div>
              </Space>

              <Space>
                <Button
                  type="text"
                  onClick={() => setIsQualityModalOpen(true)}
                  style={{ color: 'white' }}
                >
                  画质: {playerState.quality === 'high' ? '高清' :
                        playerState.quality === 'medium' ? '标清' : '流畅'}
                </Button>
                <Button
                  type="text"
                  onClick={() => handlePlaybackRateChange(
                    playerState.playbackRate === 2.0 ? 1.0 : playerState.playbackRate + 0.5
                  )}
                  style={{ color: 'white' }}
                >
                  倍速: {playerState.playbackRate}x
                </Button>
                <Button
                  type="text"
                  icon={<FullscreenOutlined />}
                  onClick={() => setPlayerState(prev => ({ ...prev, isFullscreen: !prev.isFullscreen }))}
                  style={{ color: 'white' }}
                />
              </Space>
            </div>
          </div>
        </div>
      </Card>

      {/* 视频信息和操作 */}
      {currentVideo && (
        <Card style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <Title level={4} style={{ marginBottom: 8 }}>{currentVideo.title}</Title>
              <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                <div><Text type="secondary">分辨率: </Text>{currentVideo.resolution}</div>
                <div><Text type="secondary">格式: </Text>{currentVideo.format.toUpperCase()}</div>
                <div><Text type="secondary">大小: </Text>{currentVideo.fileSize}</div>
                <div><Text type="secondary">创建时间: </Text>{currentVideo.createdAt}</div>
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <Tag color={currentVideo.hasAudio ? 'green' : 'default'}>
                  {currentVideo.hasAudio ? '有音频' : '无音频'}
                </Tag>
                <Tag color={currentVideo.hasSubtitles ? 'blue' : 'default'}>
                  {currentVideo.hasSubtitles ? '有字幕' : '无字幕'}
                </Tag>
                <Tag color={
                  currentVideo.status === 'ready' ? 'success' :
                  currentVideo.status === 'processing' ? 'processing' : 'error'
                }>
                  {currentVideo.status === 'ready' ? '就绪' :
                   currentVideo.status === 'processing' ? '处理中' : '错误'}
                </Tag>
              </div>
            </div>

            <Space>
              <Button
                icon={<HeartOutlined />}
                onClick={handleLike}
                type={currentVideo.likes > 0 ? 'primary' : 'default'}
              >
                {currentVideo.likes}
              </Button>
              <Button icon={<ShareAltOutlined />} onClick={handleShare}>
                分享
              </Button>
              <Button icon={<EyeOutlined />}>
                {currentVideo.views} 观看
              </Button>
            </Space>
          </div>
        </Card>
      )}
    </div>
  );

  // 渲染视频列表
  const renderVideoList = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3}>视频库</Title>
        <Space>
          <Input.Search placeholder="搜索视频..." style={{ width: 200 }} />
          <Select defaultValue="all" style={{ width: 120 }}>
            <Option value="all">全部状态</Option>
            <Option value="ready">就绪</Option>
            <Option value="processing">处理中</Option>
            <Option value="error">错误</Option>
          </Select>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        {previewVideos.map((video) => (
          <Col xs={24} sm={12} lg={8} key={video.id}>
            <Card
              hoverable
              cover={
                <div style={{
                  height: 160,
                  backgroundColor: '#1890ff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                }}>
                  <PlayCircleOutlined style={{ fontSize: 48 }} />
                </div>
              }
              onClick={() => handleSelectVideo(video)}
              style={{
                border: currentVideo?.id === video.id ? '2px solid #1890ff' : undefined,
                cursor: 'pointer',
              }}
            >
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text strong style={{ flex: 1 }}>{video.title}</Text>
                  <Tag color={video.status === 'ready' ? 'success' : 'processing'}>
                    {video.status === 'ready' ? '就绪' : '处理中'}
                  </Tag>
                </div>
                <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                  {video.description}
                </Text>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <div>
                  <Text type="secondary">时长: </Text>
                  <Text>{formatTime(video.duration)}</Text>
                </div>
                <div>
                  <Text type="secondary">画质: </Text>
                  <Text>{video.quality === 'high' ? '高清' : video.quality === 'medium' ? '标清' : '流畅'}</Text>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: 12 }}>
                  <div>
                    <EyeOutlined style={{ marginRight: 4 }} />
                    <Text type="secondary">{video.views}</Text>
                  </div>
                  <div>
                    <HeartOutlined style={{ marginRight: 4 }} />
                    <Text type="secondary">{video.likes}</Text>
                  </div>
                </div>
                <div>
                  <Text type="secondary">{video.fileSize}</Text>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="播放器" key="player" />
          <TabPane tab="视频库" key="library" />
          <TabPane tab="播放列表" key="playlist" />
        </Tabs>
      </div>

      {activeTab === 'player' && renderPlayer()}
      {activeTab === 'library' && renderVideoList()}
      {activeTab === 'playlist' && (
        <div>
          <Title level={3}>播放列表</Title>
          <Card>
            <List
              dataSource={playlist}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button type="link" onClick={() => {
                      const video = previewVideos.find(v => v.id === item.id);
                      if (video) handleSelectVideo(video);
                    }}>
                      播放
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<Avatar icon={<PlayCircleOutlined />} />}
                    title={item.title}
                    description={`时长: ${formatTime(item.duration)} | 顺序: ${item.order}`}
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      )}

      {/* 画质选择模态框 */}
      <Modal
        title="选择画质"
        open={isQualityModalOpen}
        onCancel={() => setIsQualityModalOpen(false)}
        footer={null}
        width={400}
      >
        <div style={{ padding: '16px 0' }}>
          {['high', 'medium', 'low'].map((quality) => (
            <div
              key={quality}
              onClick={() => handleQualityChange(quality)}
              style={{
                padding: '16px',
                marginBottom: 8,
                border: `1px solid ${
                  playerState.quality === quality ? '#1890ff' : '#d9d9d9'
                }`,
                borderRadius: 6,
                cursor: 'pointer',
                backgroundColor: playerState.quality === quality ? '#e6f7ff' : 'white',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div>
                  <Text strong>
                    {quality === 'high' ? '高清 (1080p)' :
                     quality === 'medium' ? '标清 (720p)' : '流畅 (480p)'}
                  </Text>
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary">
                      {quality === 'high' ? '最佳观看体验，推荐宽带网络' :
                       quality === 'medium' ? '平衡画质与流量' :
                       '节省流量，适合移动网络'}
                    </Text>
                  </div>
                </div>
                {playerState.quality === quality && (
                  <Tag color="blue">当前选择</Tag>
                )}
              </div>
            </div>
          ))}
        </div>
      </Modal>

      {/* 播放设置模态框 */}
      <Modal
        title="播放设置"
        open={isSettingsModalOpen}
        onCancel={() => setIsSettingsModalOpen(false)}
        footer={null}
        width={500}
      >
        <Form layout="vertical">
          <Form.Item label="默认播放速度">
            <Select
              value={playerState.playbackRate}
              onChange={(value) => setPlayerState(prev => ({ ...prev, playbackRate: value }))}
            >
              <Option value={0.5}>0.5x</Option>
              <Option value={0.75}>0.75x</Option>
              <Option value={1.0}>1.0x (正常)</Option>
              <Option value={1.25}>1.25x</Option>
              <Option value={1.5}>1.5x</Option>
              <Option value={2.0}>2.0x</Option>
            </Select>
          </Form.Item>

          <Form.Item label="默认音量">
            <Slider
              min={0}
              max={100}
              value={playerState.volume}
              onChange={(value) => setPlayerState(prev => ({ ...prev, volume: value }))}
            />
          </Form.Item>

          <Form.Item label="默认画质">
            <Select
              value={playerState.quality}
              onChange={(value) => setPlayerState(prev => ({ ...prev, quality: value }))}
            >
              <Option value="low">流畅</Option>
              <Option value="medium">标清</Option>
              <Option value="high">高清</Option>
            </Select>
          </Form.Item>

          <Form.Item label="自动播放下一集" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>

          <Form.Item label="循环播放" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Form.Item label="显示字幕" valuePropName="checked">
            <Switch defaultChecked />
          </Form.Item>

          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsSettingsModalOpen(false)}>
                取消
              </Button>
              <Button type="primary" onClick={() => {
                setIsSettingsModalOpen(false);
                message.success('播放设置已保存');
              }}>
                保存设置
              </Button>
            </Space>
          </div>
        </Form>
      </Modal>

      {/* 播放列表模态框 */}
      <Modal
        title="播放列表"
        open={isPlaylistModalOpen}
        onCancel={() => setIsPlaylistModalOpen(false)}
        footer={null}
        width={600}
      >
        <List
          dataSource={playlist}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer' }}
              onClick={() => {
                const video = previewVideos.find(v => v.id === item.id);
                if (video) {
                  handleSelectVideo(video);
                  setIsPlaylistModalOpen(false);
                }
              }}
            >
              <List.Item.Meta
                avatar={
                  <div style={{
                    width: 40,
                    height: 40,
                    backgroundColor: '#f0f0f0',
                    borderRadius: 4,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    {item.order}
                  </div>
                }
                title={item.title}
                description={`时长: ${formatTime(item.duration)}`}
              />
              {currentVideo?.id === item.id && (
                <Tag color="blue">正在播放</Tag>
              )}
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
};

export default Preview;