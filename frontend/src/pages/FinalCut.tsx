import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import { Typography, Button } from 'antd';
import {
  PlayCircleOutlined, PauseCircleOutlined, VideoCameraOutlined,
  FullscreenOutlined, SoundOutlined, MutedOutlined, DownloadOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

const FinalCut: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { loadState, restoreFromBackend, setWorkId } = usePipelinePersistence();

  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoTitle, setVideoTitle] = useState('成片');
  const [playing, setPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);

  const fmt = (t: number) => { const m = Math.floor(t / 60), s = Math.floor(t % 60); return `${m}:${s.toString().padStart(2, '0')}`; };

  useEffect(() => {
    (async () => {
      const urlWorkId = searchParams.get('workId');
      if (urlWorkId) { setWorkId(urlWorkId); await restoreFromBackend(urlWorkId); }
      let data = loadState('finalCut');
      if (!data) { const o = localStorage.getItem('final_cut_result'); if (o) try { data = JSON.parse(o); } catch {} }
      if (data?.videoUrl) {
        setVideoUrl(data.videoUrl);
        setVideoTitle(data.episodeTitle || '剪辑成片');
        if (data.duration) setDuration(data.duration);
      }
    })();
  }, []);

  return (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ height: 72, background: '#fff', borderBottom: '1px solid #e5e5ea', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 48px', flexShrink: 0 }}>
        <Text strong style={{ fontSize: 15, color: '#1d1d1f' }}>
          <VideoCameraOutlined style={{ marginRight: 6 }} />
          {videoTitle} · 成片
        </Text>
        <Button size="small" type="primary" icon={<DownloadOutlined />} disabled={!videoUrl} onClick={() => { if (videoUrl) { const a = document.createElement('a'); a.href = videoUrl; a.download = `${videoTitle}.mp4`; a.click(); } }}>导出</Button>
      </div>
      <div style={{ flex: 1, background: '#e8e8ec', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div ref={playerRef} style={{ width: '100%', maxWidth: 1500, background: '#000', borderRadius: 12, overflow: 'hidden', position: 'relative' }}>
          {videoUrl ? (
            <video ref={videoRef} src={videoUrl} style={{ width: '100%', display: 'block' }}
              onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
              onLoadedMetadata={() => videoRef.current && setDuration(videoRef.current.duration)}
              onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
          ) : (
            <div style={{ width: '100%', aspectRatio: '16/9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#555', flexDirection: 'column', gap: 12 }}>
              <VideoCameraOutlined style={{ fontSize: 64 }} />
              <Text style={{ color: '#888', fontSize: 15 }}>暂无成片</Text>
              <Text style={{ color: '#666', fontSize: 12 }}>在分镜视频页生成镜头并剪辑后，成片将在此展示</Text>
            </div>
          )}
          {videoUrl && (
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'rgba(0,0,0,0.7)', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <Button size="middle" icon={playing ? <PauseCircleOutlined /> : <PlayCircleOutlined />} onClick={() => { if (videoRef.current) { if (playing) videoRef.current.pause(); else videoRef.current.play(); setPlaying(!playing); } }} style={{ color: '#fff', fontSize: 20 }} type="text" />
              <Text style={{ color: '#fff', fontSize: 13, minWidth: 40 }}>{fmt(currentTime)}</Text>
              <div style={{ flex: 1, height: 5, background: 'rgba(255,255,255,0.2)', borderRadius: 3, cursor: 'pointer' }} onClick={(e) => { const rect = (e.target as HTMLElement).getBoundingClientRect(); const pct = (e.clientX - rect.left) / rect.width; if (videoRef.current) { videoRef.current.currentTime = pct * duration; setCurrentTime(pct * duration); } }}>
                <div style={{ width: `${(currentTime / (duration || 1)) * 100}%`, height: '100%', background: '#2563eb', borderRadius: 3, transition: 'width 0.1s' }} />
              </div>
              <Text style={{ color: '#fff', fontSize: 13, minWidth: 40 }}>{fmt(duration)}</Text>
              <Button size="middle" icon={isMuted ? <MutedOutlined /> : <SoundOutlined />} onClick={() => { if (videoRef.current) { videoRef.current.muted = !isMuted; setIsMuted(!isMuted); } }} style={{ color: '#fff' }} type="text" />
              <Button size="middle" icon={<FullscreenOutlined />} onClick={() => playerRef.current?.requestFullscreen()} style={{ color: '#fff' }} type="text" />
            </div>
          )}
        </div>
        <Text style={{ marginTop: 16, color: '#ccc', fontSize: 14 }}>{videoTitle}</Text>
      </div>
    </div>
  );
};

export default FinalCut;