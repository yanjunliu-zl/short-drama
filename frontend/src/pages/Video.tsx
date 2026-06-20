import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { finalCutService } from '@/services/finalCutService';
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
  shotNumber?: number;
  shotDescription?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  duration: number;
  resolution: string;
  format: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  fileSize?: number;
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
  const navigate = useNavigate();
  const { saveState, getWorkId, loadState, restoreFromBackend } = usePipelinePersistence();

  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isFinalCutProcessing, setIsFinalCutProcessing] = useState(false);
  const finalCutPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
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

  const [videoTasks, setVideoTasks] = useState<VideoTask[]>([]);

  // 加载视频结果：优先 localStorage，空则从后端恢复
  useEffect(() => {
    const loadData = async () => {
      let data = loadState('videoResults');
      if (!data) {
        const oldData = localStorage.getItem('shot_video_results');
        if (oldData) { try { data = JSON.parse(oldData); } catch {} }
      }
      if (!data) {
        const workId = getWorkId();
        if (workId) {
          await restoreFromBackend(workId);
          data = loadState('videoResults');
        }
      }
      if (data && data.episodes && data.episodes.length > 0) {
        try {
          setEpisodes(data.episodes.map((ep: any) => ({
            id: ep.id,
            title: ep.title,
            number: ep.number,
            description: ep.description,
          })));
          setActiveEpisodeId(data.episodes[0].id);

          // 构建视频任务列表
          const tasks: VideoTask[] = [];
          let taskIdCounter = 0;
          for (const ep of data.episodes) {
            const videoResults = ep.videoResults || [];
            for (const shot of (ep.shots || [])) {
              taskIdCounter++;
              const videoResult = videoResults.find(
                (r: any) => r.shot_id === shot.id
              );
              tasks.push({
                id: taskIdCounter,
                name: `${ep.title} - 镜头${shot.number} [${shot.shotType}]`,
                episodeId: ep.id,
                episodeTitle: ep.title,
                shotNumber: shot.number,
                shotDescription: shot.description,
                status: videoResult?.status === 'completed' ? 'completed' :
                        videoResult?.status === 'failed' ? 'failed' : 'pending',
                progress: videoResult?.status === 'completed' ? 100 : 0,
                duration: shot.duration || 5,
                resolution: '1920x1080',
                format: 'mp4',
                videoUrl: videoResult?.video_url,
                fileSize: videoResult?.file_size,
                createdAt: data.generatedAt || new Date().toISOString(),
              });
            }
          }
          setVideoTasks(tasks);
          const completedCount = tasks.filter(t => t.status === 'completed').length;
          message.success(`已加载 ${data.episodes.length} 集共 ${tasks.length} 个镜头视频（${completedCount} 个已完成）`);
          // 持久化到后端
          saveState('videoResults', data, getWorkId() || undefined);
        } catch (e) {
          console.error('Failed to load shot video results:', e);
        }
      }
    };
    loadData();
  }, []);

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

  const handleSettingsSave = (values: any) => {
    setVideoSettings({ ...videoSettings, ...values });
    setIsSettingsModalOpen(false);
    message.success('设置已保存');
  };

  // 剪辑成片 — 拼接当前集所有已完成镜头视频
  const handleFinalCut = useCallback(async () => {
    const currentTasks = videoTasks.filter(
      t => t.episodeId === activeEpisodeId && t.status === 'completed' && t.videoUrl
    );
    if (currentTasks.length === 0) {
      message.warning('当前集没有已完成的视频，请先在分镜脚本页面生成视频');
      return;
    }
    const videoUrls = currentTasks.map(t => t.videoUrl!);
    const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);

    setIsFinalCutProcessing(true);

    try {
      const response = await finalCutService.createFinalCut({
        project_id: activeEpisodeId,
        episode_title: currentEpisode?.title,
        video_urls: videoUrls,
      });

      if (response?.task_id) {
        message.info(`剪辑任务已提交，正在拼接 ${videoUrls.length} 个镜头视频...`);

        finalCutPollingRef.current = setInterval(async () => {
          try {
            const status = await finalCutService.getFinalCutStatus(response.task_id);

            if (status?.status === 'completed') {
              if (finalCutPollingRef.current) {
                clearInterval(finalCutPollingRef.current);
                finalCutPollingRef.current = null;
              }
              setIsFinalCutProcessing(false);
              message.success('剪辑完成！正在跳转到成片页面...');

              const finalCutData = {
                taskId: response.task_id,
                episodeTitle: currentEpisode?.title,
                videoUrl: status.video_url,
                thumbnailUrl: status.thumbnail_url,
                duration: status.duration,
                completedAt: new Date().toISOString(),
              };
              localStorage.setItem('final_cut_result', JSON.stringify(finalCutData));

              // 持久化到后端
              saveState('finalCut', finalCutData, getWorkId() || undefined);
              navigate('/final-cut');
            } else if (status?.status === 'failed') {
              if (finalCutPollingRef.current) {
                clearInterval(finalCutPollingRef.current);
                finalCutPollingRef.current = null;
              }
              setIsFinalCutProcessing(false);
              message.error(status.error_message || '剪辑失败');
            }
          } catch (err: any) {
            if (err?.response?.status === 404) {
              if (finalCutPollingRef.current) {
                clearInterval(finalCutPollingRef.current);
                finalCutPollingRef.current = null;
              }
              setIsFinalCutProcessing(false);
              message.error('剪辑任务已过期');
            }
          }
        }, 3000);
      } else {
        throw new Error('未获取到任务ID');
      }
    } catch (err: any) {
      setIsFinalCutProcessing(false);
      message.error(err?.response?.data?.detail || err?.message || '剪辑请求失败');
    }
  }, [videoTasks, activeEpisodeId, episodes, navigate]);

  // 清理轮询
  useEffect(() => {
    return () => {
      if (finalCutPollingRef.current) {
        clearInterval(finalCutPollingRef.current);
      }
    };
  }, []);

  const renderVideoPreview = () => {
    const currentTasks = videoTasks.filter(t => t.episodeId === activeEpisodeId);
    const firstCompleted = currentTasks.find(t => t.status === 'completed' && t.videoUrl);
    const hasMedia = !!firstCompleted;
    const isImage = hasMedia && /\.(png|jpg|jpeg|webp)(\?|$)/i.test(firstCompleted.videoUrl!);

    return (
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
        {hasMedia ? (
          isImage ? (
            <img src={firstCompleted.videoUrl} alt="预览图"
              style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          ) : (
            <video
              src={firstCompleted.videoUrl}
              controls
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              poster={firstCompleted.thumbnailUrl}
            />
          )
        ) : (
          <div style={{ textAlign: 'center' }}>
            <VideoCameraOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <div style={{ fontSize: 18, marginBottom: 8 }}>视频预览区域</div>
            <Text type="secondary">
              {videoTasks.length === 0
                ? '请先在分镜脚本页面生成视频'
                : currentTasks.length === 0
                ? '当前集暂无视频'
                : '该集暂无已完成的视频'}
            </Text>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginBottom: 24 }}>
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
          disabled={!hasMedia}
          onClick={() => {
            if (firstCompleted?.videoUrl) {
              window.open(firstCompleted.videoUrl, '_blank');
            }
          }}
        >
          下载视频
        </Button>
      </div>

      {/* 镜头选择列表 */}
      {currentTasks.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text strong>本集镜头视频：</Text>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            {currentTasks.map(task => (
              <Tag
                key={task.id}
                color={task.status === 'completed' ? 'success' : task.status === 'failed' ? 'error' : 'default'}
                style={{ cursor: task.videoUrl ? 'pointer' : 'default' }}
              >
                镜头{task.shotNumber}
                {task.status === 'completed' ? ' ✓' : task.status === 'failed' ? ' ✗' : ''}
              </Tag>
            ))}
          </div>
        </div>
      )}
    </div>
    );
  };

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
                    <Text type="secondary">镜头: </Text>
                    <Text>{task.shotNumber ? `#${task.shotNumber}` : '-'}</Text>
                  </div>
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

                {task.shotDescription && (
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">画面描述: </Text>
                    <Text style={{ fontSize: 12 }}>{task.shotDescription}</Text>
                  </div>
                )}

                {task.fileSize && (
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">文件大小: </Text>
                    <Text>{(task.fileSize / 1024 / 1024).toFixed(1)} MB</Text>
                  </div>
                )}

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
                    <CheckCircleOutlined style={{ fontSize: 32, color: '#34c759' }} />
                    <div style={{ marginTop: 8 }}>
                      {task.videoUrl && (
                        <>
                          <Button type="link" icon={<EyeOutlined />} size="small"
                            onClick={() => window.open(task.videoUrl, '_blank')}>预览</Button>
                          <Button type="link" icon={<DownloadOutlined />} size="small"
                            onClick={() => {
                              if (task.videoUrl) {
                                const a = document.createElement('a');
                                a.href = task.videoUrl!;
                                a.download = `${task.name}.mp4`;
                                a.click();
                              }
                            }}>下载</Button>
                        </>
                      )}
                      {!task.videoUrl && <Text type="secondary" style={{ fontSize: 11 }}>无视频URL</Text>}
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

  const renderGenerationLog = () => {
    const currentTasks = videoTasks.filter(t => t.episodeId === activeEpisodeId);
    const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);

    return (
    <div>
      <Title level={4}>生成日志</Title>
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: 8,
        padding: 16,
        height: 300,
        overflowY: 'auto',
        fontFamily: 'monospace',
        fontSize: 12,
      }}>
        <div style={{ marginBottom: 16 }}>
          <Text strong>当前集数：</Text>
          <Tag color="blue">{currentEpisode?.title || '无'}</Tag>
          <Text style={{ marginLeft: 16 }}>镜头总数：{currentTasks.length}</Text>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Text strong>生成任务列表：</Text>
        </div>
        {currentTasks.length === 0 ? (
          <Text type="secondary">暂无生成日志。请在分镜脚本页面点击"生成故事板"开始生成视频。</Text>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {currentTasks.map(task => (
              <li key={task.id} style={{
                marginBottom: 8,
                color: task.status === 'completed' ? '#34c759' :
                       task.status === 'failed' ? '#ff3b30' :
                       task.status === 'processing' ? '#0066cc' : '#aeaeb2'
              }}>
                <Text strong>[{new Date(task.createdAt).toLocaleTimeString()}]</Text>{' '}
                镜头{task.shotNumber} ({task.name.split('[')[1]?.replace(']', '') || '-'}){' '}
                {task.status === 'completed' ? '✓ 已完成' :
                 task.status === 'failed' ? '✗ 失败' :
                 task.status === 'processing' ? '⏳ 处理中...' : '○ 等待中'}
                {task.fileSize && task.status === 'completed'
                  ? ` (${(task.fileSize / 1024 / 1024).toFixed(1)}MB)`
                  : ''}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
    );
  };

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
            <VideoCameraOutlined style={{ marginRight: 8 }} />
            分镜视频
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>将分镜脚本生成为视频，支持预览和下载</Text>
        </div>
        <Button
          type="primary"
          size="middle"
          icon={<VideoCameraOutlined />}
          onClick={handleFinalCut}
          loading={isFinalCutProcessing}
          disabled={isFinalCutProcessing}
        >
          {isFinalCutProcessing ? '正在剪辑...' : '剪辑成片'}
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
            <Title level={5} style={{ margin: 0 }}>{episodes.find(ep => ep.id === activeEpisodeId)?.title}</Title>
          </div>
          <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
            <div style={{ marginBottom: 24 }}>
              <Space>
                <Button type={activeTab === 'preview' ? 'primary' : 'default'} icon={<PlayCircleOutlined />} onClick={() => setActiveTab('preview')}>视频预览</Button>
                <Button type={activeTab === 'tasks' ? 'primary' : 'default'} icon={<CloudUploadOutlined />} onClick={() => setActiveTab('tasks')}>生成任务</Button>
                <Button type={activeTab === 'log' ? 'primary' : 'default'} icon={<EyeOutlined />} onClick={() => setActiveTab('log')}>生成日志</Button>
              </Space>
            </div>
            <div style={{ marginTop: 24 }}>
              {activeTab === 'preview' && renderVideoPreview()}
              {activeTab === 'tasks' && renderTasks()}
              {activeTab === 'log' && renderGenerationLog()}
            </div>
          </div>
        </div>
      </div>{/* end content area */}

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
