import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
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
  Drawer,
  InputNumber,
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
  FolderOpenOutlined,
  StarOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;
const { TabPane } = Tabs;

// 视频预览类型定义
interface PreviewVideo {
  id: number;
  title: string;
  episodeId: string;
  episodeTitle: string;
  description: string;
  duration: number; // 秒
  resolution: string;
  format: string;
  url?: string;
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

// 集数类型定义
interface Episode {
  id: string;
  title: string;
  number: number;
  videos: PreviewVideo[];
  description?: string;
}

const FinalCut: React.FC = () => {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const { saveState, getWorkId, loadState, restoreFromBackend } = usePipelinePersistence();

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

  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([
    {
      id: 'ep-1',
      title: '第一集',
      number: 1,
      videos: [
        {
          id: 1,
          title: '咖啡馆对话场景',
          episodeId: 'ep-1',
          episodeTitle: '第一集',
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
          episodeId: 'ep-1',
          episodeTitle: '第一集',
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
      ],
      description: '故事的开端',
    },
    {
      id: 'ep-2',
      title: '第二集',
      number: 2,
      videos: [
        {
          id: 3,
          title: '科技实验室场景',
          episodeId: 'ep-2',
          episodeTitle: '第二集',
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
      ],
      description: '情节转折',
    },
  ]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  const playTimerRef = useRef<NodeJS.Timeout | null>(null);

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

  // 获取当前集数的视频
  const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);
  const currentVideos = currentEpisode?.videos || [];

  // 初始化当前视频
  React.useEffect(() => {
    if (currentVideos.length > 0 && !currentVideo) {
      setCurrentVideo(currentVideos[0]);
    }
  }, [currentVideos, currentVideo]);

  // 加载成片结果：优先 localStorage，空则从后端恢复
  useEffect(() => {
    const loadData = async () => {
      let data = loadState('finalCut');
      if (!data) {
        const oldData = localStorage.getItem('final_cut_result');
        if (oldData) { try { data = JSON.parse(oldData); } catch {} }
      }
      if (!data) {
        const workId = getWorkId();
        if (workId) {
          await restoreFromBackend(workId);
          data = loadState('finalCut');
        }
      }
      if (data) {
      try {
        if (data.videoUrl) {
          const realVideo: PreviewVideo = {
            id: Date.now(),
            title: data.episodeTitle || '剪辑成片',
            episodeId: 'final-cut',
            episodeTitle: data.episodeTitle || '成片',
            description: '所有镜头拼接完成的最终视频',
            duration: data.duration || 0,
            resolution: '1920x1080',
            format: 'mp4',
            url: data.videoUrl,
            thumbnailUrl: data.thumbnailUrl,
            fileSize: data.duration ? `${Math.round(data.duration)}秒` : '-',
            createdAt: data.completedAt || new Date().toISOString(),
            views: 0,
            likes: 0,
            quality: 'high',
            hasAudio: true,
            hasSubtitles: false,
            status: 'ready' as const,
          };

          // 添加到或创建"成片"集数
          const finalCutEpisode: Episode = {
            id: 'final-cut',
            title: '成片',
            number: 1,
            videos: [realVideo],
            description: '拼接完成的完整视频',
          };

          setEpisodes(prev => {
            const existing = prev.find(ep => ep.id === 'final-cut');
            if (existing) {
              return prev.map(ep => ep.id === 'final-cut'
                ? { ...ep, videos: [realVideo, ...ep.videos] }
                : ep
              );
            }
            return [finalCutEpisode, ...prev];
          });
          setActiveEpisodeId('final-cut');
          setCurrentVideo(realVideo);
          message.success('剪辑成片已完成！');
        }
        // 数据保留在 localStorage 作为缓存，不再删除
      } catch (e) {
        console.error('Failed to load final cut result:', e);
      }
    }
    }
    loadData();
  }, []);

  // 集数操作
  const handleAddEpisode = () => {
    const newEpisode: Episode = {
      id: `ep-${Date.now()}`,
      title: `第${episodes.length + 1}集`,
      number: episodes.length + 1,
      videos: [],
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

  // 播放器控制函数
  const handlePlay = () => {
    if (!currentVideo) return;
    if (videoRef.current) {
      videoRef.current.play();
      setPlayerState(prev => ({ ...prev, isPlaying: true }));
    }
  };

  const handlePause = () => {
    if (videoRef.current) {
      videoRef.current.pause();
      setPlayerState(prev => ({ ...prev, isPlaying: false }));
    }
  };

  const handleSeek = (value: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = value;
      setPlayerState(prev => ({ ...prev, currentTime: value }));
    }
  };

  const handleVolumeChange = (value: number) => {
    if (videoRef.current) {
      videoRef.current.volume = value / 100;
    }
    setPlayerState(prev => ({
      ...prev,
      volume: value,
      isMuted: value === 0
    }));
  };

  const handleToggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !videoRef.current.muted;
    }
    setPlayerState(prev => ({ ...prev, isMuted: !prev.isMuted }));
  };

  const handlePlaybackRateChange = (rate: number) => {
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
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
    const updatedVideos = currentVideos.map(video =>
      video.id === currentVideo.id
        ? { ...video, likes: video.likes + 1 }
        : video
    );
    updateEpisodeVideos(updatedVideos);
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

  // 更新当前集数的视频
  const updateEpisodeVideos = (videos: PreviewVideo[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, videos } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  // 渲染视频播放器
  const renderPlayer = () => (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={3}>
            <EyeOutlined style={{ marginRight: 12 }} />
            {currentEpisode?.title}
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
          {currentVideo?.url ? (
            <video
              ref={videoRef}
              src={currentVideo.url}
              poster={currentVideo.thumbnailUrl}
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              onTimeUpdate={() => {
                if (videoRef.current) {
                  setPlayerState(prev => ({ ...prev, currentTime: videoRef.current!.currentTime }));
                }
              }}
              onLoadedMetadata={() => {
                if (videoRef.current) {
                  setPlayerState(prev => ({ ...prev, currentTime: 0 }));
                }
              }}
              onEnded={() => {
                setPlayerState(prev => ({ ...prev, isPlaying: false }));
              }}
            />
          ) : (
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
          )}

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
                max={videoRef.current?.duration || currentVideo?.duration || 100}
                value={playerState.currentTime}
                onChange={handleSeek}
                tooltip={{ formatter: (value) => formatTime(value || 0) }}
                styles={{
                  track: { background: '#0066cc' },
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
                      track: { background: '#0066cc' },
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
                <div><Text type="secondary">集数: </Text>{currentVideo.episodeTitle}</div>
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
        {currentVideos.map((video) => (
          <Col xs={24} sm={12} lg={8} key={video.id}>
            <Card
              hoverable
              cover={
                <div style={{
                  height: 160,
                  backgroundColor: '#0066cc',
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
                border: currentVideo?.id === video.id ? '2px solid #0066cc' : undefined,
                cursor: 'pointer',
              }}
            >
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text strong style={{ flex: 1 }}>{video.title}</Text>
                  <Tag color={video.status === 'ready' ? 'success' : 'processing'}>
                    {video.status === 'ready' ? '就绪' : '处理中'}
                  </Tag>
                  <Tag color="blue" style={{ fontSize: 12, padding: '2px 8px' }}>{video.episodeTitle}</Tag>
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
      {currentVideos.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#aeaeb2' }}>
          <EyeOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无视频，点击"添加视频"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  // 渲染集数列表
  const renderEpisodeList = () => (
    <div style={{ borderRight: '1px solid #f5f5f7', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #f5f5f7' }}>
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
              backgroundColor: activeEpisodeId === episode.id ? '#e8f2fd' : 'transparent',
              borderBottom: '1px solid #f5f5f7',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StarOutlined
                  style={{
                    color: activeEpisodeId === episode.id ? '#0066cc' : '#e5e5ea',
                    fontSize: 16
                  }}
                />
                <Text strong style={{ color: activeEpisodeId === episode.id ? '#0066cc' : undefined }}>
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

      <div style={{ padding: '16px', borderTop: '1px solid #f5f5f7' }}>
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
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      {/* 顶部操作栏 */}
      <div style={{
        padding: '12px 24px', background: '#fff', borderBottom: '1px solid #e5e5ea',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <EyeOutlined style={{ marginRight: 8 }} />
            成片
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>最终视频的播放、管理与导出</Text>
        </div>
        <Button
          type="primary"
          size="middle"
          icon={<DownloadOutlined />}
          onClick={() => message.info('导出功能开发中，敬请期待')}
        >
          导出
        </Button>
      </div>

      {/* 内容区 */}
      <div style={{ flex: 1, display: 'flex', padding: '16px 24px', gap: 16, overflow: 'hidden' }}>
        {/* 左侧集数列表 */}
        <div style={{ width: 280, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          {renderEpisodeList()}
        </div>

        {/* 右侧内容区域 */}
        <div style={{ flex: 1, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid #f5f5f7' }}>
            <Tabs activeKey={activeTab} onChange={setActiveTab}>
              <TabPane tab="播放器" key="player" />
              <TabPane tab="视频库" key="library" />
              <TabPane tab="播放列表" key="playlist" />
            </Tabs>
          </div>
          <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
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
                            const video = currentVideos.find(v => v.id === item.id);
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
          </div>
        </div>
      </div>

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
                  playerState.quality === quality ? '#0066cc' : '#e5e5ea'
                }`,
                borderRadius: 6,
                cursor: 'pointer',
                backgroundColor: playerState.quality === quality ? '#e8f2fd' : 'white',
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
                const video = currentVideos.find(v => v.id === item.id);
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
                    backgroundColor: '#f5f5f7',
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
            <Input.TextArea rows={4} placeholder="描述本集的主要内容..." />
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

export default FinalCut;
