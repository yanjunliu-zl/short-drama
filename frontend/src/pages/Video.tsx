import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import {
  Typography, Button, Space, Tag, message, Radio, Select, Progress,
  Modal, Drawer, List, Upload, Input, Spin, Tooltip,
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
}
interface Episode { id: string; title: string; number: number; description?: string; }

const Video: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { saveState, getWorkId, loadState, restoreFromBackend, setWorkId } = usePipelinePersistence();

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

  const [visualStyle, setVisualStyle] = useState('2D吉卜力动画');
  const [photoStyle, setPhotoStyle] = useState('经典电影');
  const [aspectRatio, setAspectRatio] = useState('portrait');
  const [genMode, setGenMode] = useState('merge');
  const [frameMode, setFrameMode] = useState('first');
  const [clusterMode, setClusterMode] = useState(true);
  const [genAll, setGenAll] = useState(false);
  const [genProgress, setGenProgress] = useState(0);
  const [quality, setQuality] = useState('480P');
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

  const shotFrameKey = useCallback((task: VideoTask | null) => {
    if (!task) return '';
    return `${task.episodeId}_${task.shotNumber}`;
  }, []);

  const fmt = (t: number) => { const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${s.toString().padStart(2, '0')}`; };

  useEffect(() => {
    const load = async () => {
      const urlWorkId = searchParams.get('workId');
      if (urlWorkId) { setWorkId(urlWorkId); await restoreFromBackend(urlWorkId); }

      // 加载分镜数据（用于构建待生成任务列表）
      let storyData = loadState('storyboard');
      if (!storyData) { const o = localStorage.getItem('shot_generation_result'); if (o) try { storyData = JSON.parse(o); } catch {} }
      // 加载已有的视频结果
      const videoData = loadState('videoResults');

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
      const sb = loadState('storyboard') || JSON.parse(localStorage.getItem('shot_generation_result') || '{}');
      const sEp = sb?.episodes?.find((e: any) => e.id === task.episodeId);
      const shot = sEp?.shots?.find((s: any) => s.number === task.shotNumber);
      if (!shot) throw new Error('Shot not found');
      const resp = await scriptService.generateShotsVideo({ episodes: [{ ...ep, shots: [shot] }] as any, fps: 24 });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => {
        const s = await scriptService.getShotsVideoStatus(resp.task_id);
        setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, progress: s?.progress || 10 } : t));
        if (s?.status === 'completed') { clearInterval(poll); const r = await scriptService.getShotsVideoResult(resp.task_id); const fr = r.results?.[0]; setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'completed' as const, progress: 100, videoUrl: fr?.video_url, thumbnailUrl: fr?.image_url } : t)); message.success(`镜头${task.shotNumber} 生成完成`); }
        else if (s?.status === 'failed') { clearInterval(poll); setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t)); }
      }, 3000);
    } catch { setVideoTasks(prev => prev.map(t => t.id === task.id ? { ...t, status: 'failed' as const } : t)); }
  };

  const handleGenAll = async () => {
    const pts = videoTasks.filter(t => t.status === 'pending'); if (!pts.length) { message.info('没有待生成的镜头'); return; }
    setGenAll(true); setGenProgress(5);
    try {
      const epData = episodes.map(e => ({ ...e, shots: (loadState('storyboard') || JSON.parse(localStorage.getItem('shot_generation_result') || '{}'))?.episodes?.find((x: any) => x.id === e.id)?.shots || [] }));
      const resp = await scriptService.generateShotsVideo({ episodes: epData, fps: 24 });
      if (!resp?.task_id) throw new Error('No task');
      const poll = setInterval(async () => { const s = await scriptService.getShotsVideoStatus(resp.task_id); setGenProgress(s?.progress || 10); if (s?.status === 'completed') { clearInterval(poll); setGenAll(false); const r = await scriptService.getShotsVideoResult(resp.task_id); setVideoTasks(prev => prev.map(t => { const m = r.results?.find((x: any) => x.shot_id === t.shotNumber && x.episode_id === t.episodeId); return m ? { ...t, status: 'completed' as const, progress: 100, videoUrl: m.video_url, thumbnailUrl: m.image_url } : t; })); message.success('全部生成完成'); } else if (s?.status === 'failed') { clearInterval(poll); setGenAll(false); message.error('生成失败'); } }, 3000);
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
        style: visualStyle,
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
  }, [selectedTask, visualStyle, shotFrameKey]);

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
      scriptService.generatePreviewImage({ description: `多角度视图：${desc}`, category: 'scene', style: visualStyle })
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
  }, [selectedTask, visualStyle, shotFrameKey]);

  // 当前选中镜头的帧图
  const currentFrames = selectedTask ? (frameImages[shotFrameKey(selectedTask)] || {}) : {} as { firstFrame?: string; lastFrame?: string };

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Top Bar ── */}
      {/* 顶部导航栏 — 与 Script 页风格一致 */}
      <div style={{ height: 72, background: '#fff', borderBottom: '1px solid #e5e5ea', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 48px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Text strong style={{ fontSize: 15, color: '#1d1d1f' }}>
            <VideoCameraOutlined style={{ marginRight: 6 }} />
            {episodes.find(e => e.id === activeEpisodeId)?.title || '视频制作'} · 分镜视频
          </Text>
        </div>
        <Space>
          <Text style={{ color: '#86868b', fontSize: 12 }}>共 {videoTasks.length} 镜头</Text>
          <Tooltip title="将所有待生成镜头的视频批量生成并合成为成片">
            <Button size="small" type="primary" icon={<ThunderboltOutlined />} onClick={handleGenAll} loading={genAll}>
              {genAll ? `生成中 ${genProgress}%` : '剪辑成片'}
            </Button>
          </Tooltip>
        </Space>
      </div>

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
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>

          {/* Global Config Card */}
          <div style={{ background: '#fff', borderRadius: 8, padding: 12, border: '1px solid #f0f0f0', marginBottom: 8 }}>
            <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center' }}><Text style={{ width: 80, color: '#111', fontSize: 13, flexShrink: 0 }}>视觉风格</Text><Select value={visualStyle} onChange={setVisualStyle} style={{ flex: 1 }} options={['写实', '2D吉卜力动画', '3D国风', '日漫'].map(v => ({ value: v, label: v }))} /></div>
            <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center' }}><Text style={{ width: 80, color: '#111', fontSize: 13, flexShrink: 0 }}>摄影风格</Text><Select value={photoStyle} onChange={setPhotoStyle} style={{ flex: 1 }} options={['经典电影', '纪实风格', '黑色电影'].map(v => ({ value: v, label: v }))} /></div>
            <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center' }}><Text style={{ width: 80, color: '#111', fontSize: 13, flexShrink: 0 }}>画面比例</Text><Radio.Group value={aspectRatio} onChange={e => setAspectRatio(e.target.value)} size="small"><Radio.Button value="landscape">横屏</Radio.Button><Radio.Button value="portrait">竖屏</Radio.Button></Radio.Group></div>
            <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}><Text style={{ color: '#111', fontSize: 13 }}>画质</Text><Radio.Group value={quality} onChange={e => setQuality(e.target.value)} size="small"><Radio.Button value="480P">标准(480P)</Radio.Button><Radio.Button value="720P">720P</Radio.Button><Radio.Button value="1080P">1080P</Radio.Button></Radio.Group></div>
            <Text style={{ color: '#9ca3af', fontSize: 11, display: 'block', marginBottom: 6 }}>(best quality, masterpiece, 8k, high detailed:1.2), (Studio Ghibli style:1...</Text>
            <div style={{ marginBottom: 10 }}>
              <Text style={{ color: '#111', fontSize: 13, marginRight: 8 }}>首/尾帧</Text>
              <Radio.Group value={frameMode} onChange={e => setFrameMode(e.target.value)} size="small">
                <Tooltip title="只生成镜头的开场画面（第一帧）"><Radio.Button value="first">仅首帧</Radio.Button></Tooltip>
                <Tooltip title="只生成镜头的结束画面（最后一帧）"><Radio.Button value="last">仅尾帧</Radio.Button></Tooltip>
                <Tooltip title="同时生成开场和结束画面，视频过渡更流畅"><Radio.Button value="both">首+尾</Radio.Button></Tooltip>
              </Radio.Group>
            </div>
          </div>

          {/* Selected Shot Card */}
          {selectedTask && (
            <div style={{ background: '#fff', borderRadius: 8, padding: 12, border: '1px solid #f0f0f0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Tag color="blue" style={{ margin: 0 }}>分镜 #{selectedTask.shotNumber}</Tag>
                <Tag style={{ background: '#f3f4f6', border: 'none', color: '#6b7280' }}>1-1-{selectedTask.shotNumber}</Tag>
                <Tag style={{ background: '#f3f4f6', border: 'none', color: '#6b7280' }}>MS {selectedTask.shotType || '中景'}</Tag>
                <Tooltip title="重新生成该镜头的视频">
                  <Button size="small" type="link" icon={<ReloadOutlined />} onClick={() => handleGenSingle(selectedTask)} loading={selectedTask.status === 'processing'} style={{ marginLeft: 'auto', color: '#2563eb' }} />
                </Tooltip>
              </div>
              <div style={{ display: 'flex', gap: 10, marginBottom: 8 }}>
                {/* 首帧 — frameMode 为 first 或 both 时显示 */}
                {(frameMode === 'first' || frameMode === 'both') && (
                  <Tooltip title="镜头的开场画面，可上传/AI生成后点击查看大图">
                    <div style={{ width: 80, textAlign: 'center' }}>
                      <Text style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>首帧</Text>
                      <div style={{ width: 80, height: 100, background: '#f9fafb', borderRadius: 4, border: '2px solid #2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                        onClick={() => { const url = currentFrames.firstFrame || selectedTask.thumbnailUrl; if (url) window.open(url, '_blank'); }}>
                        {generatingFrame === `${shotFrameKey(selectedTask)}_first` ? (
                          <Spin indicator={<LoadingOutlined style={{ fontSize: 18 }} spin />} />
                        ) : currentFrames.firstFrame ? (
                          <img src={currentFrames.firstFrame} alt="首帧" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        ) : selectedTask.thumbnailUrl ? (
                          <img src={selectedTask.thumbnailUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        ) : (
                          <PictureOutlined style={{ fontSize: 24, color: '#ccc' }} />
                        )}
                      </div>
                    </div>
                  </Tooltip>
                )}
                {/* 尾帧 — frameMode 为 last 或 both 时显示 */}
                {(frameMode === 'last' || frameMode === 'both') && (
                  <Tooltip title="镜头的结束画面，可上传/AI生成后点击查看大图">
                    <div style={{ width: 80, textAlign: 'center' }}>
                      <Text style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>尾帧</Text>
                      <div style={{ width: 80, height: 100, background: '#f9fafb', borderRadius: 4, border: frameMode === 'last' ? '2px solid #2563eb' : '1px solid #e5e7eb', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'pointer' }}
                        onClick={() => { if (currentFrames.lastFrame) window.open(currentFrames.lastFrame, '_blank'); }}>
                        {generatingFrame === `${shotFrameKey(selectedTask)}_last` ? (
                          <Spin indicator={<LoadingOutlined style={{ fontSize: 18 }} spin />} />
                        ) : currentFrames.lastFrame ? (
                          <img src={currentFrames.lastFrame} alt="尾帧" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                        ) : (
                          <PictureOutlined style={{ fontSize: 24, color: '#ccc' }} />
                        )}
                      </div>
                    </div>
                  </Tooltip>
                )}
                {/* 视角/关键帧 */}
                <Tooltip title="上传参考图或AI生成多角度视图，辅助视频生成的一致性">
                  <div style={{ width: 80, textAlign: 'center' }}>
                    <Text style={{ color: '#6b7280', fontSize: 11, display: 'block', marginBottom: 4 }}>视角</Text>
                    <Upload
                      showUploadList={false}
                      beforeUpload={(file) => { handleUploadFrame(file, 'perspective'); return false; }}
                    >
                      <div style={{ width: 80, height: 100, border: '2px dashed #d1d5db', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#9ca3af', cursor: 'pointer' }}>
                        {perspectiveImage ? (
                          <img src={perspectiveImage} alt="视角" style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: 4 }} />
                        ) : generatingFrame?.includes('perspective') ? (
                          <LoadingOutlined style={{ fontSize: 20 }} />
                        ) : (
                          <><UploadOutlined style={{ fontSize: 18 }} /><Text style={{ fontSize: 10 }}>上传/生成</Text></>
                        )}
                      </div>
                    </Upload>
                    <Tooltip title="调用AI生成该镜头的多角度参考视图">
                      <Button size="small" type="link" style={{ fontSize: 10, padding: 0, height: 20 }}
                        onClick={() => handlePerspectiveAction('generate')}
                        loading={generatingFrame?.includes('perspective')}>
                        AI生成
                      </Button>
                    </Tooltip>
                  </div>
                </Tooltip>
                {/* 操作按钮 */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, justifyContent: 'center' }}>
                  <Tooltip title={`调用AI根据分镜描述生成${frameMode === 'first' ? '开场' : frameMode === 'last' ? '结束' : '首尾'}画面，用于视频生成参考`}>
                    <Button size="small" type="primary" ghost icon={<ThunderboltOutlined />} block
                      loading={!!generatingFrame}
                      onClick={() => {
                        if (frameMode === 'first' || frameMode === 'both') handleAIGenerateFrame('first');
                        if (frameMode === 'last' || frameMode === 'both') handleAIGenerateFrame('last');
                      }}>
                      AI 生成{frameMode === 'first' ? '首帧' : frameMode === 'last' ? '尾帧' : '首尾帧'}
                    </Button>
                  </Tooltip>
                  <Tooltip title="从角色资产库中选择角色的参考图作为帧图像">
                    <Button size="small" style={{ borderColor: '#c4b5fd', color: '#7c3aed', background: '#f5f3ff' }} block
                      icon={<UserOutlined />}
                      onClick={() => handleOpenCharLibrary(frameMode)}>
                      角色库
                    </Button>
                  </Tooltip>
                  <Tooltip title="从场景素材库中选择场景图片作为帧图像">
                    <Button size="small" type="text" block style={{ color: '#6b7280', fontSize: 11 }}
                      icon={<InboxOutlined />}
                      onClick={() => handleOpenMaterialLibrary(frameMode)}>
                      从素材库
                    </Button>
                  </Tooltip>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                <Tooltip title="根据当前首/尾帧设置重新调用AI生成帧图像">
                  <Button size="small" icon={<ReloadOutlined />} onClick={handleRegenerate} loading={!!generatingFrame}>重新生成</Button>
                </Tooltip>
                <Tooltip title="预览该镜头视频">
                  <Button size="small" icon={<CaretRightOutlined />} type="text" />
                </Tooltip>
                <Tooltip title="复制当前帧图像的URL链接">
                  <Button size="small" icon={<CopyOutlined />} type="text" onClick={handleCopyFrame} />
                </Tooltip>
                <Tooltip title="收藏当前帧到个人收藏夹">
                  <Button size="small" icon={<StarOutlined />} type="text" onClick={handleStarFrame} />
                </Tooltip>
              </div>
              <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
                <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                  <Tag color="purple" style={{ fontSize: 10 }}>剧本</Tag>
                  {frameMode !== 'last' && <Tag style={{ background: '#f3f4f6', border: 'none', fontSize: 10, color: '#6b7280' }}>首帧</Tag>}
                  {frameMode !== 'first' && <Tag style={{ background: '#f3f4f6', border: 'none', fontSize: 10, color: '#6b7280' }}>尾帧</Tag>}
                  <Tag color="green" style={{ fontSize: 10 }}>视频</Tag>
                </div>
                <Text style={{ color: '#c4b5fd', fontSize: 11 }}>剧本: {selectedTask.shotDescription?.slice(0, 40) || '暂无描述'}</Text>
              </div>
            </div>
          )}

          {/* Shot list */}
          <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {epTasks.map((t, i) => (
              <div key={t.id} onClick={() => setSelectedTask(t)} style={{ padding: '4px 10px', cursor: 'pointer', borderRadius: 4, fontSize: 12, background: selectedTask?.id === t.id ? '#2563eb' : '#f3f4f6', color: selectedTask?.id === t.id ? '#fff' : '#111' }}>
                #{i + 1} {t.shotType || '中景'}
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderTop: '1px solid #f0f0f0', padding: '8px 16px', display: 'flex', gap: 16, fontSize: 11, color: '#6b7280' }}>
          <Tooltip title="已完成 / 失败 / 待处理 / 总镜头数">✅{completed} ❌{epTasks.filter(t => t.status === 'failed').length} ⏳{pending} 共{epTasks.length}镜头</Tooltip>
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