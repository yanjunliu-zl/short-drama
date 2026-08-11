import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import { useCollaboration } from '@/hooks/useCollaboration';
import { useCredits } from '@/hooks/useCredits';
import {
  Typography, Button, Space, Tag, message, Radio, Select,
  Modal, Upload, Input, Spin, Tooltip,
} from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, VideoCameraOutlined,
  SoundOutlined, MutedOutlined, FullscreenOutlined, MoreOutlined,
  ThunderboltOutlined, LoadingOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined,
  PictureOutlined, CaretRightOutlined, UploadOutlined,
  InboxOutlined, UserOutlined, EnvironmentOutlined,
  CameraOutlined,
} from '@ant-design/icons';
import { scriptService } from '@/services/scriptService';
import { assetService, CharacterAsset, SceneTemplate } from '@/services/assetService';

const { Text } = Typography;
const { Option } = Select;

interface VideoTask {
  id: number; name: string; episodeId: string; episodeTitle: string;
  shotNumber?: number; shotDescription?: string; shotType?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number; duration: number; videoUrl?: string; thumbnailUrl?: string; fileSize?: number; createdAt: string;
  // Storyboard context
  sceneRef?: string; characters?: string[];
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
  const [videoModel, setVideoModel] = useState('comfyui');
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

  // 缩略图存储（仅作首帧兜底，无独立UI）
  const [shotThumbnails, setShotThumbnails] = useState<Record<number, string>>({});

  /** 持久化渲染页状态到 pipeline（后端 Redis + localStorage 缓存） */
  const persist = useCallback((tasks: VideoTask[], frames: Record<string, any>, thumbs: Record<number, string>) => {
    const wId = getWorkId();
    if (!wId) return;
    const payload = {
      episodes: episodes.map(ep => ({
        id: ep.id, title: ep.title, number: ep.number,
        videoResults: tasks
          .filter(t => t.episodeId === ep.id)
          .map(t => ({
            shot_id: t.shotNumber, status: t.status,
            video_url: t.videoUrl, image_url: t.thumbnailUrl,
            progress: t.progress,
          })),
      })),
      frameImages: frames,
      shotThumbnails: thumbs,
      generatedAt: new Date().toISOString(),
    };
    saveState('videoResults', payload, wId);
  }, [episodes, getWorkId, saveState]);

  const SHOT_TYPE_COLORS: Record<string, string> = {
    '远景': '#3b82f6', '全景': '#6366f1', '中景': '#10b981',
    '近景': '#f59e0b', '特写': '#ef4444', '大特写': '#dc2626',
    '过肩镜头': '#8b5cf6',
  };
  const getShotColor = (s: string) => SHOT_TYPE_COLORS[s] || '#6b7280';

  const shotFrameKey = useCallback((task: VideoTask | null) => {
    if (!task) return '';
    return `${task.episodeId}_${task.shotNumber}`;
  }, []);

  /** 构建参考图像：从 pipeline 状态收集角色和场景参考图作为一致性锚点 */
  const buildReferenceImages = useCallback(() => {
    const refs: any = { characters: {}, scenes: {}, props: {} };
    // 从 pipeline 缓存读取之前已生成的资源图（不是现生成，是读取 Scene 页持久化的结果）
    // 角色 — array of CharacterItem + reference_images（三视图）
    if (characterLock) {
      const chars = loadCached('characters');
      if (Array.isArray(chars)) {
        for (const char of chars) {
          const imgs = char.reference_images || {};
          if (imgs.front) refs.characters[char.name] = imgs.front;
          if (imgs.side) refs.characters[`${char.name}_侧脸`] = imgs.side;
          if (imgs.threeQuarter) refs.characters[`${char.name}_3/4`] = imgs.threeQuarter;
        }
      }
    }
    // 场景 — 对象格式 { list, referenceImages: { scenes: { name: url } } }
    const scns = loadCached('scenes');
    if (scns && !Array.isArray(scns)) {
      if (scns.referenceImages?.scenes) {
        Object.assign(refs.scenes, scns.referenceImages.scenes);
      }
      // 道具（如有）
      if (scns.referenceImages?.props) {
        Object.assign(refs.props, scns.referenceImages.props);
      }
    }
    return Object.keys(refs.characters).length > 0 || Object.keys(refs.scenes).length > 0 || Object.keys(refs.props).length > 0 ? refs : undefined;
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
            const r = (videoData?.episodes?.find((ve: any) => ve.id === ep.id)?.videoResults || ep.videoResults || []).find((x: any) => x.shot_id === s.number);
            tasks.push({ id: tid, name: `${ep.title} 镜头${s.number}`, episodeId: ep.id, episodeTitle: ep.title, shotNumber: s.number, shotDescription: s.description, shotType: s.shotType, sceneRef: s.sceneRef || '', characters: s.characters || [], status: (r?.status === 'completed' ? 'completed' : r?.status === 'failed' ? 'failed' : 'pending') as any, progress: r?.status === 'completed' ? 100 : 0, duration: s.duration || 5, resolution: '1920x1080', format: 'mp4', videoUrl: r?.video_url, thumbnailUrl: r?.image_url, fileSize: r?.file_size, createdAt: videoData?.generatedAt || storyData?.generatedAt || '' } as any);
          }
        }
        setVideoTasks(tasks);

        // 恢复持久化的帧图和缩略图
        if (videoData?.frameImages) setFrameImages(videoData.frameImages);
        if (videoData?.shotThumbnails) setShotThumbnails(videoData.shotThumbnails);

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
      // 注入首帧图 URL 作为 I2V 起始帧（优先使用已生成的首帧，否则用缩略图兜底）
      const sk = shotFrameKey(task);
      const currentFrames = frameImages[sk] || {};
      const firstFrameUrl = currentFrames.firstFrame || shotThumbnails[task.id];
      const shotWithFrame = { ...shot, startImageUrl: firstFrameUrl };
      const refs = buildReferenceImages();
      const resp = await scriptService.generateShotsVideo({ episodes: [{ ...ep, shots: [shotWithFrame] }] as any, fps: 24, model: videoModel, style: cineProfile, characterLock, referenceImages: refs });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => {
        try {
          const s = await scriptService.getShotsVideoStatus(resp.task_id);
          setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, progress: s?.progress || 10 } : t));
          if (s?.status === 'completed') {
            clearInterval(poll);
            console.log('[poll] completed, fetching result...', resp.task_id);
            const r = await scriptService.getShotsVideoResult(resp.task_id);
            const fr = r.results?.[0];
            console.log('[poll] result:', fr);
            let nextSingle: VideoTask[] = [];
            setVideoTasks(prev => {
              nextSingle = prev.map(t => t.id === task.id ? { ...t, status: 'completed' as const, progress: 100, videoUrl: fr?.video_url, thumbnailUrl: fr?.image_url } : t);
              const done = nextSingle.find(t => t.id === task.id);
              if (done) { setSelectedTask(done); setTimeout(() => { if (videoRef.current && done.videoUrl) { videoRef.current.src = done.videoUrl; videoRef.current.play().catch(() => {}); setPlaying(true); } }, 100); }
              return nextSingle;
            });
            setTimeout(() => persist(nextSingle, frameImages, shotThumbnails), 0);
            credits.refreshAfterDeduct();
            message.success(`镜头${task.shotNumber} 生成完成`);
          } else if (s?.status === 'failed') {
            clearInterval(poll);
            setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t));
          }
        } catch (e) { console.error('[poll] error:', e); }
      }, 3000);
    } catch { setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t)); }
  };

  const handleGenAll = async () => {
    const pts = videoTasks.filter(t => t.status === 'pending'); if (!pts.length) { message.info('没有待生成的镜头'); return; }
    setGenAll(true); setGenProgress(5);
    try {
      const sb = await loadState('storyboard', getWorkId() ?? undefined);
      // 注入首帧图 URL 到每个 shot
      const epData = episodes.map(e => {
        const epShots = sb?.episodes?.find((x: any) => x.id === e.id)?.shots || [];
        return {
          ...e,
          shots: epShots.map((s: any) => {
            const sk = `${e.id}_${s.number}`;
            const currentFrames = frameImages[sk] || {};
            // 找到对应的 VideoTask 获取缩略图兜底
            const vTask = videoTasks.find(t => t.episodeId === e.id && t.shotNumber === s.number);
            const fallbackUrl = vTask ? shotThumbnails[vTask.id] : undefined;
            return { ...s, startImageUrl: currentFrames.firstFrame || fallbackUrl };
          }),
        };
      });
      const refs = buildReferenceImages();
      const resp = await scriptService.generateShotsVideo({ episodes: epData, fps: 24, model: videoModel, style: cineProfile, characterLock, referenceImages: refs });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => { try { const s = await scriptService.getShotsVideoStatus(resp.task_id); setGenProgress(s?.progress || 10); if (s?.status === 'completed') { clearInterval(poll); setGenAll(false); console.log('[genAll] completed, fetching result...', resp.task_id); const r = await scriptService.getShotsVideoResult(resp.task_id); console.log('[genAll] result:', r); let nextAll: VideoTask[] = []; setVideoTasks(prev => { nextAll = prev.map(t => { const m = r.results?.find((x: any) => x.shot_id === t.shotNumber && x.episode_id === t.episodeId); return m ? { ...t, status: 'completed' as const, progress: 100, videoUrl: m.video_url, thumbnailUrl: m.image_url } : t; }); return nextAll; }); setTimeout(() => persist(nextAll, frameImages, shotThumbnails), 0); credits.refreshAfterDeduct(); message.success('全部生成完成'); } else if (s?.status === 'failed') { clearInterval(poll); setGenAll(false); message.error('生成失败'); } } catch (e) { console.error('[genAll] poll error:', e); } }, 3000);
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
      // 从场景/角色/道具资源库加载参考图，注入视觉锚定
      const refs = buildReferenceImages();
      const resp = await scriptService.generatePreviewImage({
        description: desc,
        category: 'scene',
        style: cineProfile,
        reference_images: refs,
        frame_type: frameType,
        shot_type: selectedTask.shotType,
        characters: selectedTask.characters,
        lighting: [selectedTask.lightingStyle, selectedTask.lightingDirection, selectedTask.colorTemperature]
          .filter(Boolean).join('，'),
        emotion: selectedTask.emotionTags,
        camera_movement: selectedTask.cameraMovement,
      });
      if (!resp?.task_id) throw new Error('No task_id');
      const poll = setInterval(async () => {
        try {
          const status = await scriptService.getPreviewImageStatus(resp.task_id);
          if (status?.status === 'completed' && status.image_url) {
            clearInterval(poll);
            let newFrames: Record<string, any> = {};
            setFrameImages(prev => {
              const sk = shotFrameKey(selectedTask);
              const cur = prev[sk] || {};
              const field = frameType === 'first' ? 'firstFrame' : 'lastFrame';
              newFrames = { ...prev, [sk]: { ...cur, [field]: status.image_url } };
              return newFrames;
            });
            setTimeout(() => persist(videoTasks, newFrames, shotThumbnails), 0);
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
  }, [selectedTask, cineProfile, shotFrameKey, buildReferenceImages]);

  /** 打开角色库 */
  const handleOpenCharLibrary = useCallback(async (frameType: string) => {
    setCharModalTarget(frameType); setCharModalOpen(true); setCharLoading(true);
    try {
      const res = await assetService.listCharacters({ limit: 200 });
      if (res?.data) {
        const seen = new Set<string>();
        const deduped = res.data.filter(c => !seen.has(c.name) && seen.add(c.name));
        setCharacters(deduped);
      }
    } catch { message.error('加载角色库失败'); }
    setCharLoading(false);
  }, []);

  /** 从角色库选择 */
  const handleSelectCharacter = useCallback((char: CharacterAsset) => {
    const imgUrl = char.reference_images && Object.values(char.reference_images)[0];
    if (!imgUrl) { message.warning('该角色暂无参考图'); return; }
    if (!selectedTask) return;
    const sk = shotFrameKey(selectedTask);
    let newFrames: Record<string, any> = {};
    setFrameImages(prev => {
      const cur = prev[sk] || {};
      const upd: any = {};
      if (charModalTarget === 'first' || charModalTarget === 'both') upd.firstFrame = imgUrl;
      if (charModalTarget === 'last' || charModalTarget === 'both') upd.lastFrame = imgUrl;
      newFrames = { ...prev, [sk]: { ...cur, ...upd } };
      return newFrames;
    });
    setTimeout(() => persist(videoTasks, newFrames, shotThumbnails), 0);
    setCharModalOpen(false);
    message.success(`已应用「${char.name}」参考图`);
  }, [selectedTask, charModalTarget, shotFrameKey, persist, videoTasks, shotThumbnails]);

  /** 打开素材库 */
  const handleOpenMaterialLibrary = useCallback(async (frameType: string) => {
    setMaterialModalTarget(frameType); setMaterialModalOpen(true); setSceneLoading(true);
    try {
      const res = await assetService.listScenes({ limit: 200 });
      if (res?.data) {
        const raw = (res.data as any).data || (res.data as any);
        const seen = new Set<string>();
        const deduped = raw.filter((s: any) => !seen.has(s.name) && seen.add(s.name));
        setScenes(deduped);
      }
    } catch { message.error('加载素材库失败'); }
    setSceneLoading(false);
  }, []);

  /** 从素材库选择 */
  const handleSelectMaterial = useCallback((scene: SceneTemplate) => {
    const imgUrl = scene.reference_images?.[0];
    if (!imgUrl) { message.warning('该场景暂无素材图'); return; }
    if (!selectedTask) return;
    const sk = shotFrameKey(selectedTask);
    let newFrames: Record<string, any> = {};
    setFrameImages(prev => {
      const cur = prev[sk] || {};
      const upd: any = {};
      if (materialModalTarget === 'first' || materialModalTarget === 'both') upd.firstFrame = imgUrl;
      if (materialModalTarget === 'last' || materialModalTarget === 'both') upd.lastFrame = imgUrl;
      newFrames = { ...prev, [sk]: { ...cur, ...upd } };
      return newFrames;
    });
    setTimeout(() => persist(videoTasks, newFrames, shotThumbnails), 0);
    setMaterialModalOpen(false);
    message.success(`已应用「${scene.name}」素材`);
  }, [selectedTask, materialModalTarget, shotFrameKey, persist, videoTasks, shotThumbnails]);

  /** 透视/视角：上传或 AI 生成 */
  const handlePerspectiveAction = useCallback((action: 'upload' | 'generate') => {
    if (action === 'upload') {
      setPerspectiveModalOpen(true);
    } else {
      if (!selectedTask) return;
      const desc = selectedTask.shotDescription || '分镜画面';
      setGeneratingFrame(`${shotFrameKey(selectedTask)}_perspective`);
      scriptService.generatePreviewImage({ description: `多角度视图：${desc}`, category: 'scene', style: cineProfile, reference_images: buildReferenceImages() })
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

  /** 更新选中镜头的参数（同步更新 selectedTask + videoTasks） */
  const updateSelectedTask = useCallback((patch: Partial<VideoTask>) => {
    setSelectedTask(prev => prev ? { ...prev, ...patch } : prev);
    setVideoTasks(prev => prev.map(t => t.id === selectedTask?.id ? { ...t, ...patch } : t));
  }, [selectedTask?.id]);

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

        {/* ── 镜头列表（紧凑） + 选中镜头详情 ── */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {epTasks.length === 0 ? (
            <Text style={{ color: '#9ca3af', fontSize: 12, padding: 20, display: 'block', textAlign: 'center' }}>暂无镜头数据</Text>
          ) : (
            <>
              {/* 选中镜头详情 + 操作 */}
              {selectedTask && (() => {
                const t = selectedTask;
                const sk = shotFrameKey(t);
                const frames = frameImages[sk] || {};
                const color = getShotColor(t.shotType || '中景');
                return (
                  <div style={{ borderTop: '2px solid #2563eb', background: '#fff', padding: '10px 12px' }}>
                    {/* 基础信息 */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                      <span style={{ background: color, color: '#fff', fontSize: 13, fontWeight: 700, padding: '2px 10px', borderRadius: 3 }}>镜头 {t.shotNumber}</span>
                      {t.sceneRef && <Tag color="green" style={{ margin: 0, fontSize: 12, fontWeight: 600 }}><EnvironmentOutlined style={{ marginRight: 2, fontSize: 10 }} />{t.sceneRef}</Tag>}
                      {t.characters?.map((c: string) => <Tag key={c} color="purple" style={{ margin: 0, fontSize: 12, fontWeight: 600 }}><UserOutlined style={{ marginRight: 2, fontSize: 10 }} />{c}</Tag>)}
                    </div>
                    {/* 描述 */}
                    {t.shotDescription && (
                      <Text style={{ fontSize: 12, fontWeight: 500, color: '#374151', display: 'block', marginBottom: 4 }}>
                        {t.shotDescription.slice(0, 80)}{t.shotDescription.length > 80 ? '…' : ''}
                      </Text>
                    )}
                    {/* 摄影参数 — 分组折叠 */}
                    <div style={{ fontSize: 10, marginBottom: 6 }}>
                      {[
                        { key: 'basic', icon: '🎬', label: '基础', defaultOpen: true, fields: [
                          { k: 'shotType', label: '景别', type: 'select', opts: Object.keys(SHOT_TYPE_COLORS) },
                          { k: 'duration', label: '时长(秒)', type: 'number', min: 1, max: 60 },
                        ]},
                        { key: 'camera', icon: '📷', label: '摄影机', defaultOpen: true, fields: [
                          { k: 'cameraRig', label: '设备', type: 'select', opts: ['三脚架','手持','斯坦尼康','滑轨','摇臂','无人机','肩扛'] },
                          { k: 'cameraMovement', label: '运镜', type: 'select', opts: ['推','拉','摇','移','跟','升','降','固定'] },
                          { k: 'movementSpeed', label: '速度', type: 'select', opts: ['缓慢流畅','自然晃动','快速','紧张晃动','极少运动'] },
                          { k: 'focalLength', label: '焦距', type: 'text' },
                        ]},
                        { key: 'lighting', icon: '💡', label: '灯光', defaultOpen: true, fields: [
                          { k: 'lightingStyle', label: '风格', type: 'select', opts: ['自然光','三点布光','高调光','低调光','侧光','逆光','霓虹光','烛光'] },
                          { k: 'lightingDirection', label: '方向', type: 'select', opts: ['正面光','侧光','逆光','顶光','底光','柔光'] },
                          { k: 'colorTemperature', label: '色温', type: 'text' },
                        ]},
                        { key: 'focus', icon: '🔍', label: '焦点', defaultOpen: true, fields: [
                          { k: 'depthOfField', label: '景深', type: 'select', opts: ['浅景深','中等景深','深景深','移焦'] },
                          { k: 'focusTarget', label: '主体', type: 'text' },
                        ]},
                        { key: 'mood', icon: '🎭', label: '情绪与氛围', defaultOpen: true, fields: [
                          { k: 'emotionTags', label: '情绪', type: 'tags' },
                          { k: 'narrativeFunction', label: '叙事', type: 'text' },
                          { k: 'atmosphericEffects', label: '氛围', type: 'select', opts: ['无','雾','雨','雪','烟','灰尘','烛光','粒子'] },
                        ]},
                      ].map(group => (
                        <details key={group.key} open={group.defaultOpen} style={{ marginBottom: 2 }}>
                          <summary style={{ cursor: 'pointer', padding: '4px 6px', borderRadius: 3, background: '#f9fafb', fontSize: 12, fontWeight: 600, color: '#111', listStyle: 'none' }}>
                            {group.icon} {group.label}
                          </summary>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px', padding: '3px 4px' }}>
                            {group.fields.map(f => {
                              const value = (t as any)[f.k];
                              const labelEl = <Text style={{ color: '#6b7280', fontSize: 11, fontWeight: 600, display: 'block' }}>{f.label}</Text>;
                              if (f.type === 'select' && f.opts) {
                                return <div key={f.k}>{labelEl}<Select size="middle" value={value || undefined} allowClear style={{ width: '100%' }} placeholder="—" onChange={(v: any) => updateSelectedTask({ [f.k]: v } as any)}>{f.opts.map((o: string) => <Option key={o} value={o}>{o}</Option>)}</Select></div>;
                              }
                              if (f.type === 'number') {
                                const nf = f as typeof f & { min?: number; max?: number };
                                return <div key={f.k}>{labelEl}<Input size="middle" type="number" min={nf.min} max={nf.max} value={value ?? (f.k === 'duration' ? 5 : '')} style={{ width: '100%' }} onChange={e => { const v = parseInt(e.target.value) || (f.k === 'duration' ? 5 : 0); updateSelectedTask({ [f.k]: f.k === 'duration' ? Math.max(1, Math.min(60, v)) : v } as any); }} /></div>;
                              }
                              if (f.type === 'tags') {
                                return <div key={f.k}>{labelEl}<Select size="middle" mode="tags" value={value || []} style={{ width: '100%' }} placeholder="—" onChange={(v: any) => updateSelectedTask({ [f.k]: v } as any)} /></div>;
                              }
                              // text
                              return <div key={f.k}>{labelEl}<Input size="middle" value={value || ''} style={{ width: '100%' }} placeholder="—" onChange={e => updateSelectedTask({ [f.k]: e.target.value } as any)} /></div>;
                            })}
                          </div>
                        </details>
                      ))}
                    </div>
                    {/* 首帧/尾帧预览 + 操作 */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      {(frameMode === 'first' || frameMode === 'both') && (
                        <div style={{ textAlign: 'center', flexShrink: 0 }}>
                          <Text style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 2 }}>首帧</Text>
                          <div style={{ width: 150, height: 188, borderRadius: 4, background: '#f9fafb', border: '2px solid #2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                            onClick={() => { const url = frames.firstFrame || t.thumbnailUrl; if (url) window.open(url, '_blank'); }}>
                            {generatingFrame === `${sk}_first` ? <LoadingOutlined style={{ fontSize: 10 }} /> :
                              frames.firstFrame ? <img src={frames.firstFrame} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                              t.thumbnailUrl ? <img src={t.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                              <PictureOutlined style={{ fontSize: 12, color: '#ccc' }} />}
                          </div>
                        </div>
                      )}
                      {(frameMode === 'last' || frameMode === 'both') && (
                        <div style={{ textAlign: 'center', flexShrink: 0 }}>
                          <Text style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 2 }}>尾帧</Text>
                          <div style={{ width: 150, height: 188, borderRadius: 4, background: '#f9fafb', border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                            onClick={() => { if (frames.lastFrame) window.open(frames.lastFrame, '_blank'); }}>
                            {generatingFrame === `${sk}_last` ? <LoadingOutlined style={{ fontSize: 10 }} /> :
                              frames.lastFrame ? <img src={frames.lastFrame} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} /> :
                              <PictureOutlined style={{ fontSize: 12, color: '#ccc' }} />}
                          </div>
                        </div>
                      )}
                      <div style={{ flex: 1 }}>
                        <Space size={4} wrap>
                          <Button size="small" type="primary" ghost icon={<ThunderboltOutlined />} loading={!!generatingFrame}
                            onClick={() => { if (frameMode === 'first' || frameMode === 'both') handleAIGenerateFrame('first'); if (frameMode === 'last' || frameMode === 'both') handleAIGenerateFrame('last'); }}>
                            AI生成帧
                          </Button>
                          <Button size="small" icon={<UserOutlined />} onClick={() => handleOpenCharLibrary(frameMode)}>角色库</Button>
                          <Button size="small" icon={<InboxOutlined />} onClick={() => handleOpenMaterialLibrary(frameMode)}>素材库</Button>
                          {t.status !== 'processing' && (
                            <Button size="small" type="primary" icon={<ThunderboltOutlined />}
                              onClick={() => handleGenSingle(t)}>
                              {t.status === 'completed' ? '重新生成' : '生成视频'}
                            </Button>
                          )}
                        </Space>
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* 紧凑镜头列表：点击选中 */}
              <div style={{ padding: '4px 6px' }}>
                {epTasks.map((t) => {
                  const isSelected = selectedTask?.id === t.id;
                  const color = getShotColor(t.shotType || '中景');
                  return (
                    <div key={t.id}
                      onClick={() => { setSelectedTask(t); if (t.videoUrl && videoRef.current) { videoRef.current.src = t.videoUrl; videoRef.current.play(); setPlaying(true); } }}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px', margin: '2px 4px 2px 0', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                        background: isSelected ? '#2563eb' : '#f3f4f6', color: isSelected ? '#fff' : '#374151',
                        border: isSelected ? '1px solid #2563eb' : '1px solid transparent' }}>
                      <span style={{ fontWeight: 700, minWidth: 16, textAlign: 'center' }}>{t.shotNumber || '?'}</span>
                      <span style={{ opacity: 0.85 }}>{t.shotType || '中景'}</span>
                      {t.status === 'completed' && <CheckCircleOutlined style={{ fontSize: 10 }} />}
                      {t.status === 'processing' && <LoadingOutlined style={{ fontSize: 10 }} />}
                      {t.status === 'failed' && <CloseCircleOutlined style={{ fontSize: 10 }} />}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

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
                <div style={{ padding: '4px 6px', textAlign: 'center', lineHeight: 1.4 }}>
                  <Text style={{ fontSize: 12, fontWeight: 700, color: '#111', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>镜头{t.shotNumber}</Text>
                  <Text style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.shotType || '中景'} · {t.duration || 5}s</Text>
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
                    <img src={Object.values(c.reference_images)[0] as string} alt={c.name} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
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
                    <img src={s.reference_images[0]} alt={s.name} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }} />
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