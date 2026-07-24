import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  Progress,
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
  ThunderboltOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { Shot, ShotEpisode, ReferenceImages } from '@/types';
import { scriptService } from '@/services/scriptService';
import { pipelineService } from '@/services/pipelineService';
import { assetService, CharacterAsset, SceneTemplate } from '@/services/assetService';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
type Episode = ShotEpisode;

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const Storyboard: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { saveState, getWorkId, loadState, restoreFromBackend, setWorkId, userId } = usePipelinePersistence();
  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  // 参考图像（角色/场景/道具 name → image_url）
  const [referenceImages, setReferenceImages] = useState<ReferenceImages>({ characters: {}, scenes: {}, props: {} });

  // 加载分镜数据：优先 URL workId → 后端 → localStorage
  useEffect(() => {
    const loadData = async () => {
      const urlWorkId = searchParams.get('workId');
      const storedWorkId = getWorkId();
      const validWorkId = urlWorkId || (storedWorkId?.startsWith('wk_') ? storedWorkId : '');
      if (validWorkId) {
        setWorkId(validWorkId);
        await restoreFromBackend(validWorkId);
      }
      // Even without valid workId, try loading from localStorage

      let data = loadState('storyboard');
      if (!data) {
        const oldData = localStorage.getItem('shot_generation_result');
        if (oldData) { try { data = JSON.parse(oldData); } catch {} }
      }

      // Load episodes from script pipeline if storyboard data is absent
      if (!data || !data.episodes || data.episodes.length === 0) {
        const scriptData = loadState('script');
        if (scriptData?.episodes?.length > 0) {
          data = { episodes: scriptData.episodes.map((ep: any) => ({
            id: ep.id || `ep-${ep.number || 1}`, title: ep.title || `第${ep.number || 1}集`,
            number: ep.number || ep.episode_number || 1, description: ep.description || ep.content || '',
            shots: [],  // No shots yet — user will generate
          })) };
        }
      }

      // 3. 展示数据
      if (data && data.episodes && data.episodes.length > 0) {
        const loadedEpisodes: Episode[] = data.episodes.map((ep: any) => ({
          id: ep.id || `ep-${ep.number}`,
          title: ep.title || `第${ep.number}集`,
          number: ep.number,
          shots: ep.shots || [],
          description: ep.description || '',
        }));
        setEpisodes(loadedEpisodes);
        setActiveEpisodeId(loadedEpisodes[0].id);
        if (data.generatedAt) {
          message.success(`已加载 ${loadedEpisodes.length} 集分镜数据`);
        }
      }

      // 加载参考图像（场景角色道具预览图，用于视频一致性）
      const savedRefs = localStorage.getItem('scene_reference_images');
      if (savedRefs) {
        try { setReferenceImages(JSON.parse(savedRefs)); } catch {}
      }
      // 也尝试从后端 pipeline state 加载
      if (urlWorkId) {
        try {
          const resp = await pipelineService.getPipelineState(urlWorkId);
          const pipeData = (resp as any)?.data;
          if (pipeData?.referenceImages) {
            setReferenceImages(pipeData.referenceImages);
            localStorage.setItem('scene_reference_images', JSON.stringify(pipeData.referenceImages));
          }
        } catch {}
      }
    };
    loadData();
  }, [searchParams]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  // 编辑状态
  const [editingShot, setEditingShot] = useState<Shot | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 视频生成状态
  const [isGeneratingVideo, setIsGeneratingVideo] = useState(false);
  const [videoGenerationProgress, setVideoGenerationProgress] = useState(0);
  const [previewingShotId, setPreviewingShotId] = useState<number | null>(null);
  const videoPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 资产选择器状态
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<string[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string>('');
  const [selectedPresetIds, setSelectedPresetIds] = useState<string[]>([]);

  // 轮询视频生成状态
  const pollVideoGeneration = useCallback((taskId: string) => {
    videoPollingRef.current = setInterval(async () => {
      try {
        const status = await scriptService.getShotsVideoStatus(taskId);
        if (status) {
          setVideoGenerationProgress(status.progress || 0);

          if (status.status === 'completed') {
            if (videoPollingRef.current) {
              clearInterval(videoPollingRef.current);
              videoPollingRef.current = null;
            }
            setIsGeneratingVideo(false);
            setVideoGenerationProgress(100);
            message.success('所有镜头视频生成完成！');

            // 获取完整结果
            const result = await scriptService.getShotsVideoResult(taskId);

            if (result.results && episodes.length > 0) {
              // 将视频 URL 关联到每个镜头
              const updatedEpisodes = episodes.map(ep => {
                const epResults = result.results.filter((r: any) => r.episode_id === ep.id);
                const updatedShots = ep.shots.map(shot => {
                  const shotResult = epResults.find((r: any) => r.shot_id === shot.id);
                  return shotResult ? { ...shot, videoUrl: shotResult.video_url } : shot;
                });
                return { ...ep, shots: updatedShots, videoResults: epResults };
              });

              // 存入 localStorage 供 Video 页面读取
              const videoData = {
                episodes: updatedEpisodes,
                taskId: taskId,
                totalShots: result.total_shots,
                completedShots: result.completed_shots,
                generatedAt: new Date().toISOString(),
              };
              localStorage.setItem('shot_video_results', JSON.stringify(videoData));

              // 持久化到后端
              saveState('videoResults', videoData, getWorkId() || undefined);

              // 导航到分镜视频页面
              navigate('/video');
            }
          } else if (status.status === 'failed') {
            if (videoPollingRef.current) {
              clearInterval(videoPollingRef.current);
              videoPollingRef.current = null;
            }
            setIsGeneratingVideo(false);
            message.error(status.error || '视频生成失败');
          }
        }
      } catch (err: any) {
        if (err?.response?.status === 404) {
          if (videoPollingRef.current) {
            clearInterval(videoPollingRef.current);
            videoPollingRef.current = null;
          }
          setIsGeneratingVideo(false);
          message.error('视频生成任务已过期，请重新生成');
        }
      }
    }, 3000);
  }, [episodes, navigate]);

  // 预览单个镜头 — 生成该镜头的视频，完成后跳转 Video 页面
  const handlePreviewShot = useCallback((shot: Shot, episode: Episode) => {
    const wId = getWorkId();
    navigate(`/video?workId=${wId || ''}&episodeId=${episode.id}&shotNumber=${shot.number}`);
  }, [navigate, getWorkId]);

  // 生成故事板 — 为每个分镜头生成视频
  const handleGenerateStoryboard = useCallback(async () => {
    if (episodes.length === 0) {
      message.warning('请先添加分镜内容');
      return;
    }

    const hasShots = episodes.some(ep => ep.shots && ep.shots.length > 0);
    if (!hasShots) {
      message.warning('请先添加分镜头');
      return;
    }

    setIsGeneratingVideo(true);
    setVideoGenerationProgress(0);

    try {
      const response = await scriptService.generateShotsVideo({
        episodes,
        referenceImages,
        style: '写实风格',
        fps: 24,
      });

      if (response?.task_id) {
        const totalShots = response.total_shots || 0;
        setVideoGenerationProgress(10);
        message.info(`视频生成任务已提交，共 ${totalShots} 个镜头，请耐心等待`);
        pollVideoGeneration(response.task_id);
      } else {
        throw new Error('未获取到任务ID');
      }
    } catch (err: any) {
      setIsGeneratingVideo(false);
      message.error(err?.response?.data?.detail || err?.message || '视频生成请求失败');
    }
  }, [episodes, pollVideoGeneration]);

  // 组件卸载时清理轮询
  useEffect(() => {
    return () => {
      if (videoPollingRef.current) {
        clearInterval(videoPollingRef.current);
      }
    };
  }, []);

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
              <Button key="preview" type="link" icon={<EyeOutlined />}
                loading={previewingShotId === shot.id}
                onClick={() => handlePreviewShot(shot, currentEpisode!)}>
                {previewingShotId === shot.id ? '生成中' : '预览'}
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
                      <div style={{ marginTop: 4, padding: 8, background: '#ffffff', borderRadius: 4 }}>
                        {shot.description}
                      </div>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <Text strong>对白/旁白：</Text>
                      <div style={{ marginTop: 4, padding: 8, background: '#f0f7ff', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
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
        <div style={{ textAlign: 'center', padding: 40, color: '#aeaeb2' }}>
          <CameraOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无分镜头，点击"添加分镜头"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  const renderTimeline = () => (
    <div style={{ marginTop: 24 }}>
      <Title level={4}>时间线概览</Title>
      <div style={{ padding: 16, background: '#ffffff', borderRadius: 8 }}>
        <div style={{ display: 'flex', overflowX: 'auto', padding: '8px 0' }}>
          {currentShots.map((shot, index) => (
            <div
              key={shot.id}
              style={{
                minWidth: 100,
                marginRight: 8,
                padding: 12,
                background: '#0066cc',
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
                  color: '#86868b',
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

  // ── Asset Selector ──
  const [charOptions, setCharOptions] = useState<{ label: string; value: string }[]>([])
  const [sceneOptions, setSceneOptions] = useState<{ label: string; value: string }[]>([])
  const [assetExpanded, setAssetExpanded] = useState(false)
  useEffect(() => {
    assetService.listCharacters({ limit: 50 }).then((res: any) => {
      if (res?.data) setCharOptions(res.data.map((c: CharacterAsset) => ({ label: `${c.name} (${c.role_type})`, value: c.asset_id })))
    }).catch(() => {})
    assetService.listScenes({ limit: 50 }).then((res: any) => {
      if (res?.data) setSceneOptions(res.data.map((s: SceneTemplate) => ({ label: `${s.name} [${s.category}]`, value: s.template_id })))
    }).catch(() => {})
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
      {/* 顶部操作栏 */}
      <div style={{
        padding: '12px 24px', background: '#fff', borderBottom: '1px solid #e5e5ea',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <CameraOutlined style={{ marginRight: 8 }} />
            分镜脚本
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>设计和编辑视频的分镜头脚本</Text>
        </div>
        <Button
          type="primary"
          size="middle"
          icon={<ThunderboltOutlined />}
          onClick={handleGenerateStoryboard}
          loading={isGeneratingVideo}
          disabled={isGeneratingVideo}
        >
          {isGeneratingVideo ? '正在生成视频...' : '生成故事板'}
        </Button>
      </div>

      {/* 视频生成进度指示 */}
      {isGeneratingVideo && (
        <div style={{
          padding: '8px 24px', background: '#f0f7ff', borderBottom: '1px solid #d6e4ff',
          textAlign: 'center',
        }}>
          <Progress percent={videoGenerationProgress} status="active" size="small" style={{ maxWidth: 400 }} />
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            <LoadingOutlined style={{ marginRight: 6 }} />
            正在为每个镜头生成视频，请稍候...
          </Text>
        </div>
      )}

      {/* 资产选择器 */}
      <div style={{ padding: '4px 24px', background: '#fafbfc', borderBottom: '1px solid #e5e5ea' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => setAssetExpanded(!assetExpanded)}>
          <Text type="secondary" style={{ fontSize: 12 }}>🎬 资产库选择</Text>
          <Text style={{ fontSize: 11, color: '#999' }}>{assetExpanded ? '收起' : '展开'}</Text>
        </div>
        {assetExpanded && (
          <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <Select mode="multiple" placeholder="选择角色资产" style={{ minWidth: 240 }}
              options={charOptions} onChange={setSelectedCharacterIds} allowClear size="small" />
            <Select placeholder="选择场景模板" style={{ minWidth: 200 }}
              options={sceneOptions} onChange={setSelectedSceneId} allowClear size="small" />
            <Button size="small" icon={<FolderOpenOutlined />} onClick={() => navigate('/assets')}>管理资产库</Button>
          </div>
        )}
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
            <Title level={5} style={{ margin: 0 }}>{currentEpisode?.title}</Title>
          </div>
          <div style={{ padding: '24px', flex: 1, overflow: 'auto' }}>
            {renderShotsList()}
            {renderTimeline()}
          </div>
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
