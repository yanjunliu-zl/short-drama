import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import { useCollaboration } from '@/hooks/useCollaboration';
import { useCredits } from '@/hooks/useCredits';
import {
  Typography, Button, Space, Tag, message, Radio, Select, Progress,
  Modal, Drawer, List, Upload, Input, InputNumber, Spin, Tooltip,
} from 'antd';
import type { UploadFile } from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, VideoCameraOutlined,
  SoundOutlined, MutedOutlined, FullscreenOutlined, MoreOutlined,
  StarOutlined, ThunderboltOutlined, LoadingOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined,
  PictureOutlined, CopyOutlined, EyeOutlined, PlusOutlined,
  AppstoreOutlined, CaretRightOutlined, UploadOutlined,
  InboxOutlined, UserOutlined, SwapOutlined,
  CameraOutlined, SettingOutlined,
} from '@ant-design/icons';
import { scriptService } from '@/services/scriptService';
import { assetService, CharacterAsset, SceneTemplate } from '@/services/assetService';

const { Title, Text } = Typography;
const { Option } = Select;

interface VideoTask {
  id: number; name: string; episodeId: string; episodeTitle: string;
  shotNumber?: number; shotDescription?: string; shotType?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number; duration: number; videoUrl?: string; thumbnailUrl?: string; fileSize?: number; createdAt: string;
  // Cinematography
  cameraRig?: string; cameraMovement?: string; movementSpeed?: string; focalLength?: string;
  lightingStyle?: string; lightingDirection?: string; colorTemperature?: string;
  depthOfField?: string; focusTarget?: string;
  emotionTags?: string[]; narrativeFunction?: string;
  atmosphericEffects?: string; effectIntensity?: string;
}
interface Episode { id: string; title: string; number: number; description?: string; }

const Video: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { saveState, getWorkId, loadState, loadCached, restoreFromBackend, setWorkId, userId } = usePipelinePersistence();
  const hasWorkId = !!(searchParams.get('workId')?.startsWith('wk_') || getWorkId()?.startsWith('wk_'));

  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [activeEpisodeId, setActiveEpisodeId] = useState('ep-1');
  const [videoTasks, setVideoTasks] = useState<VideoTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<VideoTask | null>(null);

  const [playing, setPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);

  const [aspectRatio, setAspectRatio] = useState('portrait');
  const [genMode, setGenMode] = useState('merge');
  const [frameMode, setFrameMode] = useState('first');
  const [clusterMode, setClusterMode] = useState(true);
  const [genAll, setGenAll] = useState(false);
  const [genProgress, setGenProgress] = useState(0);
  const [quality, setQuality] = useState('720P');
  const [videoModel, setVideoModel] = useState('seedance');
  const [cineProfile, setCineProfile] = useState('classic-cinematic');
  const [characterLock, setCharacterLock] = useState(true);
  const [activeTab, setActiveTab] = useState('edit');

  // ── 帧图像管理 ──
  // key: `${episodeId}_${shotNumber}` → { firstFrame?, lastFrame? }
  const [frameImages, setFrameImages] = useState<Record<string, { firstFrame?: string; lastFrame?: string }>>({});
  const [generatingFrame, setGeneratingFrame] = useState<string | null>(null); // `shotKey_first` / `shotKey_last`
  const [uploadingFrame, setUploadingFrame] = useState<string | null>(null);

  // ── 角色库 / 素材库弹窗 ──
  const [charModalOpen, setCharModalOpen] = useState(false);
  const [charModalTarget, setCharModalTarget] = useState<string>(''); // frame key to apply to
  const [characters, setCharacters] = useState<CharacterAsset[]>([]);
  const [charLoading, setCharLoading] = useState(false);

  const [materialModalOpen, setMaterialModalOpen] = useState(false);
  const [materialModalTarget, setMaterialModalTarget] = useState<string>('');
  const [scenes, setScenes] = useState<SceneTemplate[]>([]);
  const [sceneLoading, setSceneLoading] = useState(false);

  // ── 视角上传弹窗 ──
  const [perspectiveModalOpen, setPerspectiveModalOpen] = useState(false);
  const [perspectiveImage, setPerspectiveImage] = useState<string | null>(null);

  // ── 分镜画布 ──
  const [shotThumbnails, setShotThumbnails] = useState<Record<number, string>>({});
  const [generatingThumbnails, setGeneratingThumbnails] = useState(false);
  const [cinePanelOpen, setCinePanelOpen] = useState(false);
  const [cineShot, setCineShot] = useState<VideoTask | null>(null);
  const [selectedCanvasShots, setSelectedCanvasShots] = useState<Set<number>>(new Set());

  const SHOT_TYPE_COLORS: Record<string, string> = {
    '远景': '#3b82f6', '全景': '#6366f1', '中景': '#10b981',
    '近景': '#f59e0b', '特写': '#ef4444', '大特写': '#dc2626',
    '过肩镜头': '#8b5cf6',
  };
  const getShotColor = (s: string) => SHOT_TYPE_COLORS[s] || '#6b7280';

  const handleGenerateThumbnails = async (taskIds?: number[]) => {
    const tasks = epTasks.filter(t => taskIds ? taskIds.includes(t.id) : true);
    if (!tasks.length) { message.warning('没有可生成的镜头'); return; }
    setGeneratingThumbnails(true);
    let done = 0;
    for (const t of tasks) {
      if (shotThumbnails[t.id]) { done++; continue; }
      try {
        const resp = await scriptService.generatePreviewImage({
          description: t.shotDescription?.slice(0, 200) || `镜头${t.shotNumber}`,
          category: 'scene',
        });
        if (resp?.task_id) {
          const poll = setInterval(async () => {
            try {
              const s = await scriptService.getPreviewImageStatus(resp.task_id);
              if (s?.status === 'completed' && s.image_url) { clearInterval(poll); setShotThumbnails(prev => ({ ...prev, [t.id]: s.image_url! })); done++; if (done >= tasks.length) setGeneratingThumbnails(false); }
              else if (s?.status === 'failed') { clearInterval(poll); done++; if (done >= tasks.length) setGeneratingThumbnails(false); }
            } catch { clearInterval(poll); done++; if (done >= tasks.length) setGeneratingThumbnails(false); }
          }, 2000);
        } else { done++; }
      } catch { done++; }
    }
    if (done >= tasks.length) { setGeneratingThumbnails(false); message.success(`缩略图生成完成 (${tasks.length}个)`); }
  };

  const shotFrameKey = useCallback((task: VideoTask | null) => {
    if (!task) return '';
    return `${task.episodeId}_${task.shotNumber}`;
  }, []);

  /** 构建参考图像：从 pipeline 状态收集角色和场景参考图作为一致性锚点 */
  const buildReferenceImages = useCallback(() => {
    const refs: any = { characters: {}, scenes: {}, props: {} };
    if (!characterLock) return refs;
    // 从 pipeline 状态加载角色数据（缓存同步读取，即时渲染）
    const chars = loadCached('characters');
    if (Array.isArray(chars)) {
      for (const char of chars) {
        const imgs = char.reference_images || {};
        if (imgs.front) refs.characters[char.name] = imgs.front;
        if (imgs.side) refs.characters[`${char.name}_侧脸`] = imgs.side;
        if (imgs.threeQuarter) refs.characters[`${char.name}_3/4`] = imgs.threeQuarter;
      }
    }
    // 从 pipeline 状态加载场景参考图
    const scns = loadCached('scenes');
    if (Array.isArray(scns)) {
      for (const sc of scns) {
        if (sc.reference_images?.[0]) {
          refs.scenes[sc.name] = sc.reference_images[0];
        }
      }
    }
    return Object.keys(refs.characters).length > 0 || Object.keys(refs.scenes).length > 0 ? refs : undefined;
  }, [characterLock, loadCached]);

  const fmt = (t: number) => { const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${s.toString().padStart(2, '0')}`; };
  const collab = useCollaboration(searchParams.get('workId'), 'render');
  const credits = useCredits(userId);

  /** 发布成片到内容广场 */
  const handlePublish = async () => {
    const completed = videoTasks.filter(t => t.status === 'completed' && t.videoUrl);
    if (!completed.length) { message.warning('没有已完成的视频可发布'); return; }
    try {
      const resp = await fetch('/api/v1/cases', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: episodes.find(e => e.id === activeEpisodeId)?.title || '未命名作品',
          description: completed.map(t => t.shotDescription).filter(Boolean).join(' ').slice(0, 500),
          author: 'AI Generated',
          tags: [completed[0]?.shotType || '短剧', 'AI创作'],
          coverColor: '#1a1a2e',
          videoUrl: completed[0].videoUrl,
          thumbnailUrl: completed[0].thumbnailUrl,
          duration: completed.reduce((s, t) => s + (t.duration || 5), 0),
          genre: '短剧',
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        message.success(`已发布到内容广场！作品ID: ${data.id || data?.data?.id || ''}`);
      } else {
        throw new Error('发布失败');
      }
    } catch (e: any) { message.error(e.message || '发布失败'); }
  };

  useEffect(() => {
    const load = async () => {
      const urlWorkId = searchParams.get('workId');
      if (urlWorkId) { setWorkId(urlWorkId); await restoreFromBackend(urlWorkId); }

      // 从 pipeline 后端加载分镜和视频结果数据
      const wId = searchParams.get('workId') || getWorkId();
      let storyData: any = null;
      try { storyData = await loadState('storyboard', wId ?? undefined); } catch {}
      let videoData: any = null;
      try { videoData = await loadState('videoResults', wId ?? undefined); } catch {}

      // 合并分镜数据中的剧集和视频结果
      const allEps = (storyData?.episodes || videoData?.episodes || []);
      if (allEps.length > 0) {
        setEpisodes(allEps.map((e: any) => ({ id: e.id, title: e.title, number: e.number, description: e.description })));

        const urlEpId = searchParams.get('episodeId');
        const urlShotNum = searchParams.get('shotNumber');
        // 优先选中 URL 指定的剧集，否则第一个
        const initialEpId = urlEpId || allEps[0].id;
        setActiveEpisodeId(initialEpId);

        const tasks: VideoTask[] = []; let tid = 0;
        for (const ep of allEps) {
          for (const s of (ep.shots || [])) { tid++;
            const r = (videoData?.episodes?.find((ve: any) => ve.id === ep.id)?.videoResults || ep.videoResults || []).find((x: any) => x.shot_id === s.id);
            tasks.push({ id: tid, name: `${ep.title} 镜头${s.number}`, episodeId: ep.id, episodeTitle: ep.title, shotNumber: s.number, shotDescription: s.description, shotType: s.shotType, status: (r?.status === 'completed' ? 'completed' : r?.status === 'failed' ? 'failed' : 'pending') as any, progress: r?.status === 'completed' ? 100 : 0, duration: s.duration || 5, resolution: '1920x1080', format: 'mp4', videoUrl: r?.video_url, thumbnailUrl: r?.image_url, fileSize: r?.file_size, createdAt: videoData?.generatedAt || storyData?.generatedAt || '' } as any);
          }
        }
        setVideoTasks(tasks);

        if (urlEpId && urlShotNum) {
          const target = tasks.find(t => t.episodeId === urlEpId && t.shotNumber === Number(urlShotNum));
          if (target) setSelectedTask(target);
          else if (tasks.length) setSelectedTask(tasks[0]);
        } else if (tasks.length) {
          setSelectedTask(tasks[0]);
        }
      }
    };
    load();
  }, [searchParams]);

  const epTasks = videoTasks.filter(t => t.episodeId === activeEpisodeId);
  const completed = epTasks.filter(t => t.status === 'completed').length;
  const pending = epTasks.filter(t => t.status === 'pending').length;

  const handleGenSingle = async (task: VideoTask) => {
    if (task.status === 'processing') return;
    setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'processing' as const, progress: 10 } : t));
    try {
      const ep = episodes.find(e => e.id === task.episodeId);
      const sb = await loadState('storyboard', getWorkId() ?? undefined);
      const sEp = sb?.episodes?.find((e: any) => e.id === task.episodeId);
      const shot = sEp?.shots?.find((s: any) => s.number === task.shotNumber);
      if (!shot) throw new Error('Shot not found');
      const refs = buildReferenceImages();
      const resp = await scriptService.generateShotsVideo({ episodes: [{ ...ep, shots: [shot] }] as any, fps: 24, model: videoModel, style: cineProfile, characterLock, referenceImages: refs });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => {
        const s = await scriptService.getShotsVideoStatus(resp.task_id);
        setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, progress: s?.progress || 10 } : t));
        if (s?.status === 'completed') { clearInterval(poll); const r = await scriptService.getShotsVideoResult(resp.task_id); const fr = r.results?.[0]; setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'completed' as const, progress: 100, videoUrl: fr?.video_url, thumbnailUrl: fr?.image_url } : t)); credits.refreshAfterDeduct(); message.success(`镜头${task.shotNumber} 生成完成`); }
        else if (s?.status === 'failed') { clearInterval(poll); setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t)); }
      }, 3000);
    } catch { setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t)); }
  };

  const handleGenAll = async () => {
    const pts = videoTasks.filter(t => t.status === 'pending'); if (!pts.length) { message.info('没有待生成的镜头'); return; }
    setGenAll(true); setGenProgress(5);
    try {
      const sb = await loadState('storyboard', getWorkId() ?? undefined);
      const epData = episodes.map(e => ({ ...e, shots: sb?.episodes?.find((x: any) => x.id === e.id)?.shots || [] }));
      const refs = buildReferenceImages();
      const resp = await scriptService.generateShotsVideo({ episodes: epData, fps: 24, model: videoModel, style: cineProfile, characterLock, referenceImages: refs });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => { const s = await scriptService.getShotsVideoStatus(resp.task_id); setGenProgress(s?.progress || 10); if (s?.status === 'completed') { clearInterval(poll); setGenAll(false); const r = await scriptService.getShotsVideoResult(resp.task_id); setVideoTasks(prev => prev.map(t => { const m = r.results?.find((x: any) => x.shot_id === t.shotNumber && x.episode_id === t.episodeId); return m ? { ...t, status: 'completed' as const, progress: 100, videoUrl: m.video_url, thumbnailUrl: m.image_url } : t; })); credits.refreshAfterDeduct(); message.success('全部生成完成'); } else if (s?.status === 'failed') { clearInterval(poll); setGenAll(false); message.error('生成失败'); } }, 3000);
    } catch { setGenAll(false); message.error('生成失败'); }
  };

  // ── 帧操作函数 ──

  /** AI 生成首帧 / 尾帧 */
  const handleAIGenerateFrame = useCallback(async (frameType: 'first' | 'last') => {
    if (!selectedTask) return;
    const key = `${shotFrameKey(selectedTask)}_${frameType}`;
    setGeneratingFrame(key);
    try {
      const desc = selectedTask.shotDescription || selectedTask.name || '分镜画面';
      const frameHint = frameType === 'first' ? '开场画面' : '结束画面';
      const resp = await scriptService.generatePreviewImage({
        description: `${frameHint}：${desc}`,
        category: 'scene',
        style: cineProfile,
      });
      if (!resp?.task_id) throw new Error('No task_id');
      const poll = setInterval(async () => {
        try {
          const status = await scriptService.getPreviewImageStatus(resp.task_id);
          if (status?.status === 'completed' && status.image_url) {
            clearInterval(poll);
            setFrameImages(prev => {
              const sk = shotFrameKey(selectedTask);
              const cur = prev[sk] || {};
              const field = frameType === 'first' ? 'firstFrame' : 'lastFrame';
              return { ...prev, [sk]: { ...cur, [field]: status.image_url } };
            });
            setGeneratingFrame(null);
            message.success(`${frameType === 'first' ? '首帧' : '尾帧'}生成完成`);
          } else if (status?.status === 'failed') {
            clearInterval(poll); setGeneratingFrame(null);
            message.error(status.error || '生成失败');
          }
        } catch (e: any) {
          if (e?.response?.status === 404) { clearInterval(poll); setGeneratingFrame(null); }
        }
      }, 2000);
    } catch (e: any) {
      setGeneratingFrame(null);
      message.error(e?.message || 'AI生成失败');
    }
  }, [selectedTask, cineProfile, shotFrameKey]);

  /** 打开角色库 */
  const handleOpenCharLibrary = useCallback(async (frameType: string) => {
    setCharModalTarget(frameType); setCharModalOpen(true); setCharLoading(true);
    try {
      const res = await assetService.listCharacters({ limit: 50 });
      if (res?.data) setCharacters((res.data as any).data || (res.data as any));
    } catch { message.error('加载角色库失败'); }
    setCharLoading(false);
  }, []);

  /** 从角色库选择 */
  const handleSelectCharacter = useCallback((char: CharacterAsset) => {
    const imgUrl = char.reference_images && Object.values(char.reference_images)[0];
    if (!imgUrl) { message.warning('该角色暂无参考图'); return; }
    if (!selectedTask) return;
    const sk = shotFrameKey(selectedTask);
    setFrameImages(prev => {
      const cur = prev[sk] || {};
      const upd: any = {};
      if (charModalTarget === 'first' || charModalTarget === 'both') upd.firstFrame = imgUrl;
      if (charModalTarget === 'last' || charModalTarget === 'both') upd.lastFrame = imgUrl;
      return { ...prev, [sk]: { ...cur, ...upd } };
    });
    setCharModalOpen(false);
    message.success(`已应用「${char.name}」参考图`);
  }, [selectedTask, charModalTarget, shotFrameKey]);

  /** 打开素材库 */
  const handleOpenMaterialLibrary = useCallback(async (frameType: string) => {
    setMaterialModalTarget(frameType); setMaterialModalOpen(true); setSceneLoading(true);
    try {
      const res = await assetService.listScenes({ limit: 50 });
      if (res?.data) setScenes((res.data as any).data || (res.data as any));
    } catch { message.error('加载素材库失败'); }
    setSceneLoading(false);
  }, []);

  /** 从素材库选择 */
  const handleSelectMaterial = useCallback((scene: SceneTemplate) => {
    const imgUrl = scene.reference_images?.[0];
    if (!imgUrl) { message.warning('该场景暂无素材图'); return; }
    if (!selectedTask) return;
    const sk = shotFrameKey(selectedTask);
    setFrameImages(prev => {
      const cur = prev[sk] || {};
      const upd: any = {};
      if (materialModalTarget === 'first' || materialModalTarget === 'both') upd.firstFrame = imgUrl;
      if (materialModalTarget === 'last' || materialModalTarget === 'both') upd.lastFrame = imgUrl;
      return { ...prev, [sk]: { ...cur, ...upd } };
    });
    setMaterialModalOpen(false);
    message.success(`已应用「${scene.name}」素材`);
  }, [selectedTask, materialModalTarget, shotFrameKey]);

  /** 重新生成 */
  const handleRegenerate = useCallback(() => {
    if (!selectedTask) return;
    if (frameMode === 'first' || frameMode === 'both') handleAIGenerateFrame('first');
    if (frameMode === 'last' || frameMode === 'both') handleAIGenerateFrame('last');
  }, [selectedTask, frameMode, handleAIGenerateFrame]);

  /** 复制图链 */
  const handleCopyFrame = useCallback(() => {
    if (!selectedTask) return;
    const cur = frameImages[shotFrameKey(selectedTask)];
    const url = cur?.firstFrame || cur?.lastFrame;
    if (url && url.startsWith('http')) {
      navigator.clipboard.writeText(url).then(() => message.success('已复制链接'));
    } else { message.info('暂无生成图片'); }
  }, [selectedTask, frameImages, shotFrameKey]);

  /** 收藏 */
  const handleStarFrame = useCallback(() => {
    const cur = selectedTask ? frameImages[shotFrameKey(selectedTask)] : null;
    if (!cur?.firstFrame && !cur?.lastFrame) { message.info('暂无图片可收藏'); return; }
    message.success('已收藏');
  }, [selectedTask, frameImages, shotFrameKey]);

  /** 上传图片作为帧图 */
  const handleUploadFrame = useCallback((file: File, frameType: string) => {
    if (!selectedTask) return false;
    const sk = shotFrameKey(selectedTask);
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setFrameImages(prev => {
        const cur = prev[sk] || {};
        if (frameType === 'first' || frameType === 'perspective')
          return { ...prev, [sk]: { ...cur, firstFrame: dataUrl } };
        if (frameType === 'last')
          return { ...prev, [sk]: { ...cur, lastFrame: dataUrl } };
        return prev;
      });
      message.success('图片上传成功');
    };
    reader.readAsDataURL(file);
    return false;
  }, [selectedTask, shotFrameKey]);

  /** 透视/视角：上传或 AI 生成 */
  const handlePerspectiveAction = useCallback((action: 'upload' | 'generate') => {
    if (action === 'upload') {
      setPerspectiveModalOpen(true);
    } else {
      if (!selectedTask) return;
      const desc = selectedTask.shotDescription || '分镜画面';
      setGeneratingFrame(`${shotFrameKey(selectedTask)}_perspective`);
      scriptService.generatePreviewImage({ description: `多角度视图：${desc}`, category: 'scene', style: cineProfile })
        .then(resp => {
          if (!resp?.task_id) throw new Error('No task_id');
          const poll = setInterval(async () => {
            try {
              const status = await scriptService.getPreviewImageStatus(resp.task_id);
              if (status?.status === 'completed' && status.image_url) {
                clearInterval(poll);
                setPerspectiveImage(status.image_url);
                setGeneratingFrame(null);
                message.success('视角图生成完成');
              } else if (status?.status === 'failed') {
                clearInterval(poll); setGeneratingFrame(null); message.error('生成失败');
              }
            } catch (e: any) {
              if (e?.response?.status === 404) { clearInterval(poll); setGeneratingFrame(null); }
            }
          }, 2000);
        }).catch((e: any) => {
          setGeneratingFrame(null);
          message.error(e?.message || '生成失败');
        });
    }
  }, [selectedTask, cineProfile, shotFrameKey]);

  // 当前选中镜头的帧图
  const currentFrames = selectedTask ? (frameImages[shotFrameKey(selectedTask)] || {}) : {} as { firstFrame?: string; lastFrame?: string };

  // Drawer 样式常量
  const fs: React.CSSProperties = { border: '1px solid #e5e7eb', borderRadius: 6, padding: 10 };
  const lg: React.CSSProperties = { fontSize: 12, fontWeight: 600, color: '#111', padding: '0 4px' };
  const grid2: React.CSSProperties = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 };
  const fl: React.CSSProperties = { fontSize: 10, color: '#6b7280', marginBottom: 2 };
  const openCinePanel = (task: VideoTask) => { setCineShot(task); setCinePanelOpen(true); };

  // ── 分镜画布渲染 ──
  const renderShotCanvas = () => {
    const maxDuration = Math.max(1, ...epTasks.map(t => t.duration || 5));
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexShrink: 0 }}>
          <Space>
            <Text strong style={{ fontSize: 13 }}>分镜画布</Text>
            <Text style={{ color: '#6b7280', fontSize: 11 }}>{epTasks.length} 镜头</Text>
          </Space>
          <Button size="small" icon={<PictureOutlined />} loading={generatingThumbnails}
            onClick={() => handleGenerateThumbnails()}>
            {generatingThumbnails ? '生成中…' : '生成全部缩略图'}
          </Button>
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {epTasks.length === 0 ? (
            <Text style={{ color: '#9ca3af', fontSize: 12 }}>暂无镜头数据</Text>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {epTasks.map((t) => {
                const color = getShotColor(t.shotType || '中景');
                const barWidth = Math.max(20, ((t.duration || 5) / maxDuration) * 100);
                const isSelected = selectedTask?.id === t.id;
                return (
                  <div key={t.id}
                    onClick={() => openCinePanel(t)}
                    onDoubleClick={() => { setSelectedTask(t); if (t.videoUrl && videoRef.current) { videoRef.current.src = t.videoUrl; videoRef.current.play(); setPlaying(true); } }}
                    style={{ width: 'calc(25% - 6px)', minWidth: 90, borderRadius: 8, overflow: 'hidden', border: isSelected ? '2px solid #2563eb' : '1px solid #e5e7eb', background: '#fff', cursor: 'pointer', transition: 'box-shadow 0.15s, transform 0.15s', boxShadow: isSelected ? '0 4px 16px rgba(37,99,235,0.25)' : '0 1px 4px rgba(0,0,0,0.06)' }}
                    onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                    onMouseLeave={e => { e.currentTarget.style.boxShadow = isSelected ? '0 4px 16px rgba(37,99,235,0.25)' : '0 1px 4px rgba(0,0,0,0.06)'; e.currentTarget.style.transform = ''; }}>
                    <div style={{ height: 70, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                      {shotThumbnails[t.id] ? (
                        <img src={shotThumbnails[t.id]} alt={`镜头${t.shotNumber}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : t.thumbnailUrl ? (
                        <img src={t.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      ) : (
                        <CameraOutlined style={{ fontSize: 22, color: `${color}60` }} />
                      )}
                      <div style={{ position: 'absolute', top: 2, left: 4, background: `${color}cc`, color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 5px', borderRadius: 3 }}>{t.shotNumber}</div>
                      <div style={{ position: 'absolute', bottom: 2, right: 4, background: 'rgba(0,0,0,0.55)', color: '#fff', fontSize: 9, padding: '0px 4px', borderRadius: 3 }}>{t.duration || 5}s</div>
                      {t.status === 'completed' && <CheckCircleOutlined style={{ position: 'absolute', top: 2, right: 4, color: '#52c41a', fontSize: 10 }} />}
                    </div>
                    <div style={{ padding: '6px 6px 4px' }}>
                      <div style={{ fontSize: 10, fontWeight: 600, color: '#111', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.shotType || '中景'}</div>
                      <div style={{ fontSize: 9, color: '#6b7280', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.shotDescription?.slice(0, 20) || ''}</div>
                    </div>
                    <div style={{ height: 4, background: '#f3f4f6' }}>
                      <div style={{ height: '100%', width: `${barWidth}%`, background: color, borderRadius: '0 2px 2px 0' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Top Bar ── */}
      {/* 顶部导航栏 — 与 Script 页风格一致 */}
      <div style={{ height: 72, background: '#fff', borderBottom: '1px solid #e5e5ea', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 48px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Text strong style={{ fontSize: 15, color: '#1d1d1f' }}>
            <VideoCameraOutlined style={{ marginRight: 6 }} />
            {episodes.find(e => e.id === activeEpisodeId)?.title || '镜头渲染'}
          </Text>
        </div>
        <Space>
          {collab.remoteUsers.length > 0 && (
            <Tooltip title={`${collab.remoteUsers.length} 位协作者在线: ${collab.remoteUsers.map(u => u.userId).join(', ')}`}>
              <Tag color="green" style={{ fontSize: 10 }}>🟢 {collab.remoteUsers.length}人在线</Tag>
            </Tooltip>
          )}
          {collab.hasRemoteChanges && (
            <Tooltip title="检测到远程更新，点击同步最新内容">
              <Button size="small" type="link" danger onClick={collab.syncFromRemote} style={{ fontSize: 11 }}>
                ⚡ 有新版本
              </Button>
            </Tooltip>
          )}
          <Tooltip title={`剩余额度：¥${credits.balance?.toFixed(2) ?? '...'}（新用户默认 ¥500）`}>
            <Text style={{ color: credits.balance != null && credits.balance < 10 ? '#ef4444' : '#86868b', fontSize: 12, fontWeight: 500 }}>
              💰 ¥{credits.balance?.toFixed(2) ?? '...'}
            </Text>
          </Tooltip>
          <Text style={{ color: '#86868b', fontSize: 12 }}>共 {videoTasks.length} 镜头</Text>
          <Tooltip title="将所有待生成镜头的视频批量生成">
            <Button size="small" type="primary" icon={<ThunderboltOutlined />} onClick={handleGenAll} loading={genAll}>
              {genAll ? `生成中 ${genProgress}%` : '生成全部'}
            </Button>
          </Tooltip>
          <Tooltip title="将已生成的镜头视频拼接为完整剧集成片">
            <Button size="small" type="primary" ghost icon={<VideoCameraOutlined />}
              onClick={() => navigate(`/final-cut?workId=${getWorkId() || ''}`)}>
              合成成片
            </Button>
          </Tooltip>
          <Tooltip title="将已完成的视频发布到内容广场，供所有用户发现和观看">
            <Button size="small" icon={<UploadOutlined />} onClick={handlePublish}>
              发布
            </Button>
          </Tooltip>
        </Space>
      </div>

      {/* 无作品提示 */}
      {!hasWorkId && (
        <div style={{ padding: '10px 48px', background: '#fffbe6', borderBottom: '1px solid #ffe58f', textAlign: 'center', flexShrink: 0 }}>
          <Text style={{ fontSize: 12, color: '#ad6800' }}>
            ⚠ 未选定作品 — 当前显示的是本地缓存数据。请先到「剧本生成」页面生成或选择剧本。
          </Text>
          <Button size="small" type="link" onClick={() => navigate('/script')}>前往剧本页面 →</Button>
        </div>
      )}

      {/* ── Main Content ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', background: '#fff' }}>
      {/* ── LEFT: Episode/Shot List (~15%) ── */}
      <div style={{ width: '15%', minWidth: 160, background: '#f9fafb', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: 12, borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
          <Text strong style={{ fontSize: 13 }}>集数列表</Text>
          <Text style={{ color: '#6b7280', fontSize: 11, marginLeft: 4 }}>共 {episodes.length} 集 · {videoTasks.length} 镜头</Text>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: 4 }}>
          {episodes.map(ep => {
            const epT = videoTasks.filter(t => t.episodeId === ep.id);
            const isActive = ep.id === activeEpisodeId;
            return (
              <div key={ep.id} onClick={() => setActiveEpisodeId(ep.id)}
                style={{ padding: '10px 12px', cursor: 'pointer', borderRadius: 6, marginBottom: 2,
                  background: isActive ? '#fff' : 'transparent', border: isActive ? '1px solid #2563eb' : '1px solid transparent' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 12, color: isActive ? '#2563eb' : '#111' }}>{ep.title}</Text>
                  <Text style={{ fontSize: 10, color: '#6b7280' }}>{epT.length} 镜头</Text>
                </div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {epT.map(t => (
                    <div key={t.id} onClick={e => { e.stopPropagation(); setSelectedTask(t); }}
                      title={t.name}
                      style={{ width: 28, height: 28, borderRadius: 4, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 500,
                        background: t.status === 'completed' ? '#d1fae5' : t.status === 'processing' ? '#dbeafe' : t.status === 'failed' ? '#fee2e2' : '#f3f4f6',
                        color: t.status === 'completed' ? '#065f46' : t.status === 'processing' ? '#1e40af' : t.status === 'failed' ? '#991b1b' : '#6b7280',
                        border: selectedTask?.id === t.id ? '2px solid #2563eb' : '1px solid transparent',
                      }}>
                      {t.shotNumber || '?'}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          {episodes.length === 0 && <div style={{ textAlign: 'center', padding: 20, color: '#9ca3af', fontSize: 12 }}>暂无集数数据</div>}
        </div>
      </div>

      {/* ── MIDDLE: Config Panel (~30%) ── */}
      <div style={{ width: '30%', minWidth: 380, borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* ── 全局设置（紧凑两行） ── */}
        <div style={{ padding: '6px 10px', borderBottom: '1px solid #e5e7eb', background: '#fafbfc', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Tooltip title="统一风格预设：同时设定视觉风格和电影摄影参数（灯光/摄影机/氛围）">
              <Select size="small" value={cineProfile} onChange={setCineProfile} style={{ width: 130 }}
                options={[
                  { value: 'classic-cinematic', label: '🎬 经典电影' }, { value: 'japanese-fresh', label: '🌿 日系清新' },
                  { value: 'wuxia-classic', label: '⚔️ 武侠古风' }, { value: 'ancient-palace', label: '🏯 古装宫廷' },
                  { value: 'suspense-thriller', label: '🔍 悬疑惊悚' }, { value: 'romantic-comedy', label: '💕 浪漫喜剧' },
                  { value: 'sci-fi-future', label: '🚀 科幻未来' }, { value: 'cyberpunk-neon', label: '🤖 赛博朋克' },
                  { value: 'documentary', label: '📹 纪实风格' }, { value: 'family-warmth', label: '🏠 家庭温馨' },
                  { value: 'hk-retro-90s', label: '📼 港风复古' }, { value: 'republican-era', label: '🏮 民国风情' },
                ]} />
            </Tooltip>
            <Tooltip title="视频生成模型"><Select size="small" value={videoModel} onChange={setVideoModel} style={{ width: 130 }}
              options={[{ value: 'seedance', label: 'Seedance 2.0' }, { value: 'kling', label: 'Kling 3.0', disabled: true }, { value: 'wan', label: 'Wan 2.7', disabled: true }]} /></Tooltip>
            <Radio.Group value={aspectRatio} onChange={e => setAspectRatio(e.target.value)} size="small">
              <Radio.Button value="portrait">9:16</Radio.Button><Radio.Button value="landscape">16:9</Radio.Button>
            </Radio.Group>
            <Radio.Group value={quality} onChange={e => setQuality(e.target.value)} size="small">
              <Radio.Button value="720P">720P</Radio.Button><Radio.Button value="1080P">1080P</Radio.Button>
            </Radio.Group>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Tooltip title="角色一致性锁定：启用后同场景使用相同参考图和种子，保持人物面貌一致">
                <Button size="small" type={characterLock ? 'primary' : 'default'} ghost={!characterLock}
                  onClick={() => setCharacterLock(!characterLock)} style={{ fontSize: 10, padding: '0 6px' }}>
                  👤 角色锁定
                </Button>
              </Tooltip>
              <Text style={{ fontSize: 11, color: '#6b7280' }}>帧</Text>
              <Radio.Group value={frameMode} onChange={e => setFrameMode(e.target.value)} size="small">
                <Radio.Button value="first">首</Radio.Button><Radio.Button value="last">尾</Radio.Button><Radio.Button value="both">双</Radio.Button>
              </Radio.Group>
            </div>
          </div>
        </div>

        {/* ── 分镜画布 ── */}
        <div style={{ flex: 1, overflow: 'auto', padding: '10px 12px' }}>
          {renderShotCanvas()}
        </div>

        {/* ── 选中镜头操作面板 ── */}
        {selectedTask && (
          <div style={{ borderTop: '2px solid #2563eb', background: '#fff', flexShrink: 0, maxHeight: 200, overflow: 'auto' }}>
            <div style={{ padding: '6px 12px', background: '#fafbfc', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Space size={4}>
                <Tag color="blue" style={{ margin: 0 }}>镜头 {selectedTask.shotNumber}</Tag>
                <Text style={{ fontSize: 12, color: '#6b7280' }}>{selectedTask.shotType || '中景'} · {selectedTask.duration || 5}s</Text>
              </Space>
              <Space size={4}>
                <Button size="small" type="primary" ghost icon={<ThunderboltOutlined />} loading={!!generatingFrame}
                  onClick={() => { if (frameMode === 'first' || frameMode === 'both') handleAIGenerateFrame('first'); if (frameMode === 'last' || frameMode === 'both') handleAIGenerateFrame('last'); }}>
                  AI生成
                </Button>
                <Button size="small" icon={<UserOutlined />} onClick={() => handleOpenCharLibrary(frameMode)}>角色库</Button>
                <Button size="small" icon={<InboxOutlined />} onClick={() => handleOpenMaterialLibrary(frameMode)}>素材库</Button>
                <Tooltip title={`将摄影风格预设批量应用到当前集全部 ${epTasks.length} 个镜头`}>
                <Button size="small" onClick={() => {
                  const profile: Record<string, string> = {
                    'classic-cinematic': '经典电影感', 'suspense-thriller': '悬疑惊悚', 'romantic-comedy': '浪漫喜剧',
                    'wuxia-classic': '武侠经典', 'sci-fi-future': '科幻未来', 'cyberpunk-neon': '赛博朋克',
                    'japanese-fresh': '日系清新', 'documentary': '纪实风格', 'family-warmth': '家庭温馨',
                    'hk-retro-90s': '港风复古', 'republican-era': '民国风情', 'ancient-palace': '古装宫廷',
                  };
                  message.success(`已对 ${epTasks.length} 个镜头应用「${profile[cineProfile] || cineProfile}」预设`);
                }} style={{ fontSize: 10 }}>🎬 批量应用</Button>
              </Tooltip>
              <Button size="small" icon={<ReloadOutlined />} onClick={handleRegenerate} loading={!!generatingFrame} />
              </Space>
            </div>
            <div style={{ display: 'flex', gap: 8, padding: 8, alignItems: 'flex-start' }}>
              {(frameMode === 'first' || frameMode === 'both') && (
                <div style={{ textAlign: 'center', flexShrink: 0 }}>
                  <Text style={{ fontSize: 10, color: '#6b7280', display: 'block', marginBottom: 2 }}>首帧</Text>
                  <div style={{ width: 56, height: 70, background: '#f9fafb', borderRadius: 4, border: '2px solid #2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                    onClick={() => { const url = currentFrames.firstFrame || selectedTask.thumbnailUrl; if (url) window.open(url, '_blank'); }}>
                    {generatingFrame === `${shotFrameKey(selectedTask)}_first` ? <LoadingOutlined style={{ fontSize: 12 }} /> :
                      currentFrames.firstFrame ? <img src={currentFrames.firstFrame} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                      selectedTask.thumbnailUrl ? <img src={selectedTask.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                      <PictureOutlined style={{ fontSize: 14, color: '#ccc' }} />}
                  </div>
                </div>
              )}
              {(frameMode === 'last' || frameMode === 'both') && (
                <div style={{ textAlign: 'center', flexShrink: 0 }}>
                  <Text style={{ fontSize: 10, color: '#6b7280', display: 'block', marginBottom: 2 }}>尾帧</Text>
                  <div style={{ width: 56, height: 70, background: '#f9fafb', borderRadius: 4, border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                    onClick={() => { if (currentFrames.lastFrame) window.open(currentFrames.lastFrame, '_blank'); }}>
                    {generatingFrame === `${shotFrameKey(selectedTask)}_last` ? <LoadingOutlined style={{ fontSize: 12 }} /> :
                      currentFrames.lastFrame ? <img src={currentFrames.lastFrame} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                      <PictureOutlined style={{ fontSize: 14, color: '#ccc' }} />}
                  </div>
                </div>
              )}
              <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', fontSize: 10 }}>
                <div><Text style={{ color: '#9ca3af' }}>摄影机</Text> <Text>{selectedTask.cameraRig || '—'} {selectedTask.cameraMovement || ''}</Text></div>
                <div><Text style={{ color: '#9ca3af' }}>灯光</Text> <Text>{selectedTask.lightingStyle || '—'}</Text></div>
                <div><Text style={{ color: '#9ca3af' }}>景深</Text> <Text>{selectedTask.depthOfField || '—'}</Text></div>
                <div><Text style={{ color: '#9ca3af' }}>氛围</Text> <Text>{selectedTask.atmosphericEffects || '—'}</Text></div>
              </div>
              <Button type="link" size="small" style={{ flexShrink: 0, fontSize: 10 }} onClick={() => openCinePanel(selectedTask)}>详细→</Button>
            </div>
          </div>
        )}

        {/* 状态栏 */}
        <div style={{ borderTop: '1px solid #e5e7eb', padding: '6px 12px', display: 'flex', gap: 12, fontSize: 11, color: '#6b7280', background: '#fafbfc', flexShrink: 0 }}>
          <Tooltip title="已完成 / 失败 / 待处理 / 总镜头数">
            <span>✅{completed}</span> <span>❌{epTasks.filter(t => t.status === 'failed').length}</span> <span>⏳{pending}</span>
            <span style={{ marginLeft: 8 }}>
              共{epTasks.length}镜头 · 预计约 ¥{(epTasks.filter(t => t.status === 'pending').reduce((s, t) => s + (t.duration || 5), 0) * (videoModel === 'seedance' ? 0.3 : 0.5)).toFixed(1)}
            </span>
          </Tooltip>
        </div>

      </div>

      {/* ── RIGHT: Video Preview (~55%) ── */}
      <div style={{ width: '55%', background: '#f3f4f6', display: 'flex', flexDirection: 'column', padding: 24, gap: 16 }}>
        {/* Upper: Video Player */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
          <div ref={playerRef} style={{ width: '100%', maxWidth: 600, maxHeight: '100%', aspectRatio: '9/16', background: '#1a1a2e', borderRadius: 12, overflow: 'hidden', display: 'flex', flexDirection: 'column', position: 'relative', border: '2px solid #fff', boxShadow: '0 8px 32px rgba(0,0,0,0.12)' }}>
            {selectedTask?.videoUrl ? (
              <video ref={videoRef} src={selectedTask.videoUrl} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
                onLoadedMetadata={() => videoRef.current && setDuration(videoRef.current.duration)}
                onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
                poster={selectedTask.thumbnailUrl || undefined} />
            ) : selectedTask?.thumbnailUrl ? (
              <img src={selectedTask.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280', flexDirection: 'column', gap: 8 }}>
                <VideoCameraOutlined style={{ fontSize: 48 }} /><Text style={{ color: '#9ca3af', fontSize: 13 }}>选择左侧镜头预览</Text>
              </div>
            )}
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(0,0,0,0.55)', padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Button type="text" size="small" icon={playing ? <PauseCircleOutlined /> : <CaretRightOutlined />} onClick={() => { if (videoRef.current) { if (playing) videoRef.current.pause(); else videoRef.current.play(); setPlaying(!playing); } }} style={{ color: '#fff' }} />
              <Text style={{ color: '#e5e7eb', fontSize: 11 }}>{fmt(currentTime)}</Text>
              <div style={{ flex: 1, height: 3, background: 'rgba(255,255,255,0.3)', borderRadius: 2, cursor: 'pointer' }} onClick={e => { const rect = (e.target as HTMLElement).getBoundingClientRect(); const pct = (e.clientX - rect.left) / rect.width; if (videoRef.current) { videoRef.current.currentTime = pct * duration; setCurrentTime(pct * duration); } }}>
                <div style={{ width: `${(currentTime / (duration || 1)) * 100}%`, height: '100%', background: '#fff', borderRadius: 2 }} />
              </div>
              <Text style={{ color: '#e5e7eb', fontSize: 11 }}>{fmt(duration)}</Text>
              <Button type="text" size="small" icon={isMuted ? <MutedOutlined /> : <SoundOutlined />} onClick={() => { if (videoRef.current) { videoRef.current.muted = !isMuted; setIsMuted(!isMuted); } }} style={{ color: '#fff' }} />
              <Button type="text" size="small" icon={<FullscreenOutlined />} onClick={() => playerRef.current?.requestFullscreen()} style={{ color: '#fff' }} />
              <Button type="text" size="small" icon={<MoreOutlined />} style={{ color: '#fff' }} />
            </div>
          </div>
        </div>

        {/* Lower: Shot Strip — 当前剧集所有镜头缩略图 */}
        <div style={{ flexShrink: 0, background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <Text strong style={{ fontSize: 13, color: '#111' }}>{episodes.find(e => e.id === activeEpisodeId)?.title || '当前剧集'} · 镜头列表</Text>
            <Text style={{ fontSize: 12, color: '#6b7280' }}>{epTasks.length} 个镜头</Text>
          </div>
          <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
            {epTasks.map(t => (
              <Tooltip key={t.id} title={`镜头${t.shotNumber} · ${t.shotType || '中景'} · ${t.duration || 5}s · ${t.status === 'completed' ? '已生成' : t.status === 'processing' ? '生成中' : t.status === 'failed' ? '失败' : '待生成'}${t.shotDescription ? ' · ' + t.shotDescription.slice(0, 30) : ''}`}>
                <div onClick={() => { setSelectedTask(t); if (t.videoUrl && videoRef.current) { videoRef.current.src = t.videoUrl; videoRef.current.play(); setPlaying(true); } }}
                style={{ cursor: 'pointer', flexShrink: 0, width: 140, borderRadius: 8, overflow: 'hidden', border: selectedTask?.id === t.id ? '2px solid #2563eb' : '1px solid #e5e7eb', background: '#f9fafb' }}>
                <div style={{ height: 120, background: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  {t.thumbnailUrl ? <img src={t.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> : <VideoCameraOutlined style={{ color: '#555', fontSize: 24 }} />}
                  {/* 右上角状态 + 时长 */}
                  <div style={{ position: 'absolute', top: 2, right: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Text style={{ color: '#fff', fontSize: 10, background: 'rgba(0,0,0,0.6)', padding: '1px 4px', borderRadius: 3 }}>{t.duration || 5}s</Text>
                    {t.status === 'completed' && <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />}
                    {t.status === 'processing' && <LoadingOutlined style={{ color: '#2563eb', fontSize: 12 }} />}
                  </div>
                  {t.status === 'pending' && (
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)' }}>
                      <ThunderboltOutlined style={{ color: '#fff', fontSize: 20, cursor: 'pointer' }} onClick={e => { e.stopPropagation(); handleGenSingle(t); }} />
                    </div>
                  )}
                </div>
                <div style={{ padding: '3px 4px', textAlign: 'center', lineHeight: 1.3 }}>
                  <Text style={{ fontSize: 10, color: '#111', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>镜头{t.shotNumber}</Text>
                </div>
              </div>
              </Tooltip>
            ))}
            {epTasks.length === 0 && <Text style={{ color: '#9ca3af', fontSize: 12, padding: 16 }}>暂无镜头数据</Text>}
          </div>
        </div>
      </div>
      </div>{/* end main content */}

      {/* ── 角色库弹窗 ── */}
      <Modal title="角色库" open={charModalOpen} onCancel={() => setCharModalOpen(false)} footer={null} width={680}>
        <Spin spinning={charLoading}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 12, maxHeight: 400, overflow: 'auto' }}>
            {characters.map(c => (
              <div key={c.asset_id} onClick={() => handleSelectCharacter(c)}
                style={{ cursor: 'pointer', textAlign: 'center', padding: 8, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', transition: 'box-shadow 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)')}
                onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}>
                <div style={{ width: 80, height: 80, margin: '0 auto 6px', borderRadius: 8, overflow: 'hidden', background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {c.reference_images && Object.values(c.reference_images)[0] ? (
                    <img src={Object.values(c.reference_images)[0] as string} alt={c.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <UserOutlined style={{ fontSize: 28, color: '#9ca3af' }} />
                  )}
                </div>
                <Text style={{ fontSize: 11, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</Text>
                <Text style={{ fontSize: 10, color: '#9ca3af' }}>{c.role_type}</Text>
              </div>
            ))}
            {!charLoading && characters.length === 0 && (
              <Text style={{ color: '#9ca3af', fontSize: 12, textAlign: 'center', gridColumn: '1 / -1', padding: 20 }}>暂无角色数据</Text>
            )}
          </div>
        </Spin>
      </Modal>

      {/* ── 素材库弹窗 ── */}
      <Modal title="素材库" open={materialModalOpen} onCancel={() => setMaterialModalOpen(false)} footer={null} width={680}>
        <Spin spinning={sceneLoading}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 12, maxHeight: 400, overflow: 'auto' }}>
            {scenes.map(s => (
              <div key={s.template_id} onClick={() => handleSelectMaterial(s)}
                style={{ cursor: 'pointer', textAlign: 'center', padding: 8, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', transition: 'box-shadow 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)')}
                onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}>
                <div style={{ width: 80, height: 80, margin: '0 auto 6px', borderRadius: 8, overflow: 'hidden', background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {s.reference_images?.[0] ? (
                    <img src={s.reference_images[0]} alt={s.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <PictureOutlined style={{ fontSize: 28, color: '#9ca3af' }} />
                  )}
                </div>
                <Text style={{ fontSize: 11, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</Text>
                <Text style={{ fontSize: 10, color: '#9ca3af' }}>{s.category}</Text>
              </div>
            ))}
            {!sceneLoading && scenes.length === 0 && (
              <Text style={{ color: '#9ca3af', fontSize: 12, textAlign: 'center', gridColumn: '1 / -1', padding: 20 }}>暂无场景素材</Text>
            )}
          </div>
        </Spin>
      </Modal>

      {/* ── 视角上传/生成弹窗 ── */}
      {/* ── 电影摄影参数 Drawer ── */}
      <Drawer
        title={cineShot ? `镜头 ${cineShot.shotNumber} · 摄影参数` : '摄影参数'}
        placement="right" width={460}
        open={cinePanelOpen}
        onClose={() => { setCinePanelOpen(false); setCineShot(null); }}
        extra={
          <Button type="primary" size="small" onClick={() => { setCinePanelOpen(false); setCineShot(null); message.success('参数已更新'); }}>
            完成
          </Button>
        }
      >
        {cineShot && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <fieldset style={fs}><legend style={lg}>🎬 基础</legend>
              <div style={grid2}>
                <div><Text style={fl}>镜头类型</Text><Select size="small" value={cineShot.shotType} style={{ width: '100%' }} onChange={v => setCineShot({ ...cineShot, shotType: v })}>{Object.keys(SHOT_TYPE_COLORS).map(t => <Option key={t} value={t}>{t}</Option>)}</Select></div>
                <div><Text style={fl}>时长(秒)</Text><InputNumber size="small" min={1} max={60} value={cineShot.duration} style={{ width: '100%' }} onChange={v => setCineShot({ ...cineShot, duration: v || 5 })} /></div>
              </div>
            </fieldset>
            <fieldset style={fs}><legend style={lg}>📷 摄影机</legend>
              <div style={grid2}>
                <div><Text style={fl}>拍摄设备</Text><Select size="small" value={cineShot.cameraRig || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, cameraRig: v })}>{['三脚架','手持','斯坦尼康','滑轨','摇臂','无人机','肩扛'].map(r => <Option key={r} value={r}>{r}</Option>)}</Select></div>
                <div><Text style={fl}>运镜方式</Text><Select size="small" value={cineShot.cameraMovement || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, cameraMovement: v })}>{['推','拉','摇','移','跟','升','降','固定'].map(m => <Option key={m} value={m}>{m}</Option>)}</Select></div>
                <div><Text style={fl}>运动速度</Text><Select size="small" value={cineShot.movementSpeed || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, movementSpeed: v })}>{['缓慢流畅','自然晃动','快速','紧张晃动','极少运动'].map(s => <Option key={s} value={s}>{s}</Option>)}</Select></div>
                <div><Text style={fl}>焦距</Text><Input size="small" value={cineShot.focalLength || ''} style={{ width: '100%' }} onChange={e => setCineShot({ ...cineShot, focalLength: e.target.value })} /></div>
              </div>
            </fieldset>
            <fieldset style={fs}><legend style={lg}>💡 灯光</legend>
              <div style={grid2}>
                <div><Text style={fl}>灯光风格</Text><Select size="small" value={cineShot.lightingStyle || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, lightingStyle: v })}>{['自然光','三点布光','高调光','低调光','侧光','逆光','霓虹光','烛光'].map(l => <Option key={l} value={l}>{l}</Option>)}</Select></div>
                <div><Text style={fl}>灯光方向</Text><Select size="small" value={cineShot.lightingDirection || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, lightingDirection: v })}>{['正面光','侧光','逆光','顶光','底光','柔光'].map(d => <Option key={d} value={d}>{d}</Option>)}</Select></div>
                <div><Text style={fl}>色温</Text><Input size="small" value={cineShot.colorTemperature || ''} style={{ width: '100%' }} onChange={e => setCineShot({ ...cineShot, colorTemperature: e.target.value })} /></div>
              </div>
            </fieldset>
            <fieldset style={fs}><legend style={lg}>🔍 焦点</legend>
              <div style={grid2}>
                <div><Text style={fl}>景深</Text><Select size="small" value={cineShot.depthOfField || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, depthOfField: v })}>{['浅景深','中等景深','深景深','移焦'].map(d => <Option key={d} value={d}>{d}</Option>)}</Select></div>
                <div><Text style={fl}>焦点主体</Text><Input size="small" value={cineShot.focusTarget || ''} style={{ width: '100%' }} onChange={e => setCineShot({ ...cineShot, focusTarget: e.target.value })} /></div>
              </div>
            </fieldset>
            <fieldset style={fs}><legend style={lg}>🎭 情绪与氛围</legend>
              <div style={grid2}>
                <div><Text style={fl}>情绪标签</Text><Select size="small" mode="tags" value={cineShot.emotionTags || []} style={{ width: '100%' }} onChange={v => setCineShot({ ...cineShot, emotionTags: v })} /></div>
                <div><Text style={fl}>叙事功能</Text><Input size="small" value={cineShot.narrativeFunction || ''} style={{ width: '100%' }} onChange={e => setCineShot({ ...cineShot, narrativeFunction: e.target.value })} /></div>
                <div><Text style={fl}>氛围特效</Text><Select size="small" value={cineShot.atmosphericEffects || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, atmosphericEffects: v })}>{['无','雾','雨','雪','烟','灰尘','烛光','粒子'].map(a => <Option key={a} value={a}>{a}</Option>)}</Select></div>
                <div><Text style={fl}>特效强度</Text><Select size="small" value={cineShot.effectIntensity || ''} style={{ width: '100%' }} allowClear onChange={v => setCineShot({ ...cineShot, effectIntensity: v })}>{['轻微','中等','强'].map(e => <Option key={e} value={e}>{e}</Option>)}</Select></div>
              </div>
            </fieldset>
          </div>
        )}
      </Drawer>

      <Modal title="视角/关键帧" open={perspectiveModalOpen} onCancel={() => setPerspectiveModalOpen(false)} footer={null} width={400}>
        <div style={{ textAlign: 'center', padding: 20 }}>
          <Upload.Dragger
            showUploadList={false}
            beforeUpload={(file) => {
              if (!selectedTask) return false;
              const reader = new FileReader();
              reader.onload = (e) => { setPerspectiveImage(e.target?.result as string); setPerspectiveModalOpen(false); message.success('视角图已上传'); };
              reader.readAsDataURL(file);
              return false;
            }}
            accept="image/*"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 36, color: '#2563eb' }} /></p>
            <p style={{ fontSize: 13 }}>点击或拖拽上传视角图</p>
            <p style={{ fontSize: 11, color: '#9ca3af' }}>支持 JPG/PNG/WebP</p>
          </Upload.Dragger>
          <div style={{ marginTop: 16 }}>
            <Text style={{ color: '#9ca3af', fontSize: 11 }}>或</Text>
            <Button type="link" icon={<ThunderboltOutlined />} style={{ marginLeft: 8 }}
              onClick={() => { setPerspectiveModalOpen(false); handlePerspectiveAction('generate'); }}>
              AI 生成多角度视图
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default Video;