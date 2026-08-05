import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import { useCollaboration } from '@/hooks/useCollaboration';
import { finalCutService } from '@/services/finalCutService';
import type { FinalCutStatusResponse } from '@/services/finalCutService';
import {
  Typography, Button, Card, Tag, Space, Progress, message,
  Tooltip, Spin, Modal, Row, Col,
} from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, VideoCameraOutlined,
  FullscreenOutlined, SoundOutlined, MutedOutlined, DownloadOutlined,
  ThunderboltOutlined, CheckCircleOutlined, CloseCircleOutlined,
  LoadingOutlined, ClockCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

interface ShotInfo {
  id: number; number: number;
  shotType: string; duration: number;
  description: string;
  videoUrl?: string; status?: string;
}

interface EpisodeInfo {
  id: string; title: string; number: number;
  shots: ShotInfo[];
}

const FinalCut: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { saveState, loadState, loadCached, restoreFromBackend, getWorkId, setWorkId } = usePipelinePersistence();
  const workId = searchParams.get('workId') || getWorkId() || '';
  const hasWorkId = !!(workId?.startsWith('wk_'));
  const collab = useCollaboration(workId, 'final-cut');

  const [episodes, setEpisodes] = useState<EpisodeInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Player state
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoTitle, setVideoTitle] = useState('成片');
  const [playing, setPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);

  // Stitch task state per episode: `${epId}` → task info
  const [stitchTasks, setStitchTasks] = useState<Record<string, {
    taskId: string; status: string; progress: number;
    videoUrl?: string; error?: string;
  }>>({});
  const pollingRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const fmt = (t: number) => { const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${s.toString().padStart(2, '0')}`; };

  // ── Load pipeline data ──
  useEffect(() => {
    (async () => {
      if (workId?.startsWith('wk_')) {
        setWorkId(workId);
        await restoreFromBackend(workId);
      }

      // Load shots from storyboard + video URLs from videoResults
      const storyboard = loadCached('storyboard');
      const videoResults = loadCached('videoResults');

      const eps: EpisodeInfo[] = [];
      if (storyboard?.episodes?.length) {
        for (const ep of storyboard.episodes) {
          const shots: ShotInfo[] = (ep.shots || []).map((s: any) => ({
            id: s.id, number: s.number || s.id,
            shotType: s.shotType || '中景',
            duration: s.duration || 5,
            description: s.description || '',
          }));
          eps.push({ id: ep.id, title: ep.title, number: ep.number, shots });
        }
      }
      // Merge video URLs from videoResults
      if (videoResults?.episodes?.length) {
        for (const ep of videoResults.episodes) {
          const target = eps.find(e => e.id === ep.id);
          if (target && ep.shots) {
            for (const s of ep.shots) {
              const ts = target.shots.find(x => x.number === s.shotNumber);
              if (ts && s.videoUrl) {
                ts.videoUrl = s.videoUrl;
                ts.status = s.status || 'completed';
              }
            }
          }
        }
      }
      setEpisodes(eps);

      // Check for existing final-cut result
      const fc = loadCached('finalCut');
      if (fc?.videoUrl) {
        setVideoUrl(fc.videoUrl);
        setVideoTitle(fc.episodeTitle || '成片');
      }

      setLoading(false);
    })();

    return () => {
      // Cleanup polling
      Object.values(pollingRefs.current).forEach(clearInterval);
    };
  }, []);

  // ── Stitch episode ──
  const handleStitchEpisode = useCallback(async (ep: EpisodeInfo) => {
    const completedShots = ep.shots.filter(s => s.videoUrl && s.status === 'completed');
    if (completedShots.length < 2) {
      message.warning(`「${ep.title}」只有 ${completedShots.length} 个已完成的镜头，至少需要 2 个才能合成`);
      return;
    }

    const missingCount = ep.shots.length - completedShots.length;
    if (missingCount > 0) {
      await new Promise<void>((resolve) => {
        Modal.confirm({
          title: `确认合成「${ep.title}」`,
          content: `${ep.shots.length} 个镜头中有 ${missingCount} 个未完成，将使用 ${completedShots.length} 个已完成镜头合成。`,
          onOk: () => resolve(),
          onCancel: () => resolve(),
        });
      });
    }

    const videoUrls = completedShots
      .sort((a, b) => a.number - b.number)
      .map(s => s.videoUrl!);

    try {
      const resp = await finalCutService.createFinalCut({
        project_id: workId,
        episode_title: ep.title,
        video_urls: videoUrls,
      });

      const taskId = resp.task_id;
      setStitchTasks(prev => ({
        ...prev,
        [ep.id]: { taskId, status: 'pending', progress: 0 },
      }));

      // Poll status
      const poll = setInterval(async () => {
        try {
          const status = await finalCutService.getStatus(taskId);
          setStitchTasks(prev => ({
            ...prev,
            [ep.id]: {
              taskId,
              status: status.status,
              progress: status.progress || 0,
              videoUrl: status.video_url,
              error: status.error_message,
            },
          }));

          if (status.status === 'completed' && status.video_url) {
            clearInterval(poll);
            delete pollingRefs.current[ep.id];
            message.success(`「${ep.title}」合成完成！`);
            setVideoUrl(status.video_url);
            setVideoTitle(ep.title);
            // Save to pipeline
            saveState('finalCut', {
              videoUrl: status.video_url,
              thumbnailUrl: status.thumbnail_url,
              episodeId: ep.id,
              episodeTitle: ep.title,
              taskId,
              generatedAt: new Date().toISOString(),
            }, workId);
          } else if (status.status === 'failed') {
            clearInterval(poll);
            delete pollingRefs.current[ep.id];
            message.error(`合成失败: ${status.error_message || '未知错误'}`);
          }
        } catch (err) {
          clearInterval(poll);
          delete pollingRefs.current[ep.id];
          setStitchTasks(prev => ({
            ...prev,
            [ep.id]: { ...prev[ep.id], status: 'failed', error: '状态查询失败' },
          }));
        }
      }, 3000);

      pollingRefs.current[ep.id] = poll;
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '提交合成任务失败');
    }
  }, [workId, saveState]);

  // ── Calculate totals ──
  const totalShots = episodes.reduce((s, e) => s + e.shots.length, 0);
  const completedShots = episodes.reduce(
    (s, e) => s + e.shots.filter(x => x.status === 'completed').length, 0
  );
  const pendingShots = totalShots - completedShots;

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>;
  }

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Top Bar ── */}
      <div style={{ height: 72, background: '#fff', borderBottom: '1px solid #e5e5ea', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 48px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Text strong style={{ fontSize: 15, color: '#1d1d1f' }}>
            <VideoCameraOutlined style={{ marginRight: 6 }} />
            {videoTitle} · 成片
          </Text>
          {collab.remoteUsers.length > 0 && (
            <Tooltip title={`${collab.remoteUsers.length} 位协作者在线`}>
              <Tag color="green" style={{ fontSize: 10 }}>🟢 {collab.remoteUsers.length}人在线</Tag>
            </Tooltip>
          )}
        </div>
        <Space>
          <Text style={{ color: '#86868b', fontSize: 12 }}>
            {completedShots}/{totalShots} 镜头已生成
          </Text>
          <Button size="small" icon={<DownloadOutlined />} disabled={!videoUrl}
            onClick={() => { if (videoUrl) { const a = document.createElement('a'); a.href = videoUrl; a.download = `${videoTitle}.mp4`; a.click(); } }}>
            导出
          </Button>
        </Space>
      </div>

      {/* ── Warning ── */}
      {!hasWorkId && (
        <div style={{ padding: '10px 48px', background: '#fffbe6', borderBottom: '1px solid #ffe58f', textAlign: 'center', flexShrink: 0 }}>
          <Text style={{ fontSize: 12, color: '#ad6800' }}>
            ⚠ 未选定作品 — 当前显示的是本地缓存数据。请先在「剧本生成」页面选择作品。
          </Text>
          <Button size="small" type="link" onClick={() => navigate('/script')}>前往剧本页面 →</Button>
        </div>
      )}

      {/* ── Main Content ── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', background: '#f5f5f7' }}>
        {/* LEFT: Episode list (~35%) */}
        <div style={{ width: '35%', minWidth: 360, background: '#fff', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid #e5e7eb', background: '#fafbfc' }}>
            <Title level={5} style={{ margin: 0 }}>
              <VideoCameraOutlined style={{ marginRight: 8 }} />
              剧集合成
            </Title>
            <Text type="secondary" style={{ fontSize: 12 }}>
              共 {episodes.length} 集 · {completedShots}/{totalShots} 镜头可用
            </Text>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
            {episodes.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 60, color: '#86868b' }}>
                <VideoCameraOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.4 }} />
                <p style={{ fontSize: 14, marginBottom: 4 }}>暂无数据</p>
                <p style={{ fontSize: 12, color: '#aeaeb2' }}>
                  请先在「镜头渲染」页面生成镜头视频，再回到此页面合成
                </p>
                <Button type="primary" size="small" onClick={() => navigate('/render')}>
                  前往镜头渲染 →
                </Button>
              </div>
            ) : (
              episodes.map(ep => {
                const task = stitchTasks[ep.id];
                const doneCount = ep.shots.filter(s => s.status === 'completed').length;
                const hasRunning = task && (task.status === 'pending' || task.status === 'processing');
                const isDone = task?.status === 'completed';

                return (
                  <Card key={ep.id} size="small"
                    style={{ marginBottom: 8, border: isDone ? '1px solid #52c41a' : undefined }}
                    bodyStyle={{ padding: 12 }}>
                    <Row align="middle" justify="space-between">
                      <Col flex="auto">
                        <Text strong style={{ fontSize: 13 }}>{ep.title}</Text>
                        <div style={{ marginTop: 4 }}>
                          <Space size={4}>
                            <Tag color="blue">{ep.shots.length} 镜头</Tag>
                            <Tag color={doneCount === ep.shots.length ? 'green' : doneCount > 0 ? 'orange' : 'default'}>
                              {doneCount}/{ep.shots.length} 完成
                            </Tag>
                            {ep.shots.length - doneCount > 0 && (
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {ep.shots.length - doneCount} 个待生成
                              </Text>
                            )}
                          </Space>
                        </div>
                      </Col>
                      <Col>
                        {isDone ? (
                          <Button size="small" type="link" icon={<PlayCircleOutlined />}
                            onClick={() => { setVideoUrl(task!.videoUrl!); setVideoTitle(ep.title); }}>
                            播放
                          </Button>
                        ) : hasRunning ? (
                          <div style={{ textAlign: 'center' }}>
                            <Progress percent={task!.progress} size="small" style={{ width: 80, marginBottom: 2 }} />
                            <Text style={{ fontSize: 10, color: '#2563eb', display: 'block' }}>
                              <LoadingOutlined /> {task!.status === 'pending' ? '排队中' : '拼接中'}
                            </Text>
                          </div>
                        ) : (
                          <Tooltip title={doneCount < 2 ? '至少需要 2 个完成的镜头' : '拼接已完成镜头为完整剧集'}>
                            <Button size="small" type="primary" ghost
                              icon={doneCount >= 2 ? <ThunderboltOutlined /> : <ClockCircleOutlined />}
                              onClick={() => handleStitchEpisode(ep)}
                              disabled={doneCount < 2}>
                              合成成片
                            </Button>
                          </Tooltip>
                        )}
                      </Col>
                    </Row>
                    {task?.status === 'failed' && (
                      <div style={{ marginTop: 6 }}>
                        <Space>
                          <CloseCircleOutlined style={{ color: '#ef4444', fontSize: 12 }} />
                          <Text type="danger" style={{ fontSize: 11 }}>{task.error || '合成失败'}</Text>
                          <Button size="small" type="link" danger icon={<ReloadOutlined />}
                            onClick={() => handleStitchEpisode(ep)} style={{ fontSize: 11, padding: 0 }}>
                            重试
                          </Button>
                        </Space>
                      </div>
                    )}
                  </Card>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT: Video Player (~65%) */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, minHeight: 0 }}>
          <div ref={playerRef}
            style={{
              width: '100%', maxWidth: 900, maxHeight: '100%',
              background: '#000', borderRadius: 12, overflow: 'hidden',
              position: 'relative', boxShadow: '0 8px 32px rgba(0,0,0,0.15)',
            }}>
            {videoUrl ? (
              <video ref={videoRef} src={videoUrl} style={{ width: '100%', display: 'block' }}
                onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
                onLoadedMetadata={() => videoRef.current && setDuration(videoRef.current.duration)}
                onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
                onEnded={() => setPlaying(false)} />
            ) : (
              <div style={{ width: '100%', aspectRatio: '16/9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#555', flexDirection: 'column', gap: 12 }}>
                <VideoCameraOutlined style={{ fontSize: 64 }} />
                <Text style={{ color: '#888', fontSize: 15 }}>暂无成片</Text>
                <Text style={{ color: '#666', fontSize: 12 }}>
                  {episodes.length === 0
                    ? '在「镜头渲染」页面生成镜头视频后，返回此页合成'
                    : '点击左侧剧集的「合成成片」按钮，拼接完整剧集'}
                </Text>
              </div>
            )}
            {videoUrl && (
              <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(0,0,0,0.7)', padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <Button size="small" icon={playing ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                  onClick={() => { if (videoRef.current) { if (playing) videoRef.current.pause(); else videoRef.current.play(); setPlaying(!playing); } }}
                  style={{ color: '#fff' }} type="text" />
                <Text style={{ color: '#fff', fontSize: 12, minWidth: 36 }}>{fmt(currentTime)}</Text>
                <div style={{ flex: 1, height: 4, background: 'rgba(255,255,255,0.2)', borderRadius: 2, cursor: 'pointer' }}
                  onClick={(e) => {
                    const rect = (e.target as HTMLElement).getBoundingClientRect();
                    const pct = (e.clientX - rect.left) / rect.width;
                    if (videoRef.current) { videoRef.current.currentTime = pct * duration; setCurrentTime(pct * duration); }
                  }}>
                  <div style={{ width: `${(currentTime / (duration || 1)) * 100}%`, height: '100%', background: '#2563eb', borderRadius: 2 }} />
                </div>
                <Text style={{ color: '#fff', fontSize: 12, minWidth: 36 }}>{fmt(duration)}</Text>
                <Button size="small" icon={isMuted ? <MutedOutlined /> : <SoundOutlined />}
                  onClick={() => { if (videoRef.current) { videoRef.current.muted = !isMuted; setIsMuted(!isMuted); } }}
                  style={{ color: '#fff' }} type="text" />
                <Button size="small" icon={<FullscreenOutlined />}
                  onClick={() => playerRef.current?.requestFullscreen()} style={{ color: '#fff' }} type="text" />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FinalCut;
