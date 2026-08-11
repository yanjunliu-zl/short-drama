import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card,
  Typography,
  Input,
  Button,
  List,
  Avatar,
  Space,
  Divider,
  Tabs,
  Form,
  InputNumber,
  Select,
  message,
  Row,
  Col,
  Modal,
  Tag,
  Drawer,
  Upload,
  Progress,
  Empty,
  Spin,
  Dropdown,
  Alert,
} from 'antd';
import { usePipelinePersistence, clearPipelineStorage } from '@/hooks/usePipelinePersistence';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  FileTextOutlined,
  UserOutlined,
  EnvironmentOutlined,
  ClockCircleOutlined,
  SaveOutlined,
  StarOutlined,
  FolderOpenOutlined,
  PlayCircleOutlined,
  BookOutlined,
  BulbOutlined,
  InboxOutlined,
  ArrowLeftOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SettingOutlined,
  ExperimentOutlined,
  DownloadOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { scriptService } from '@/services/scriptService';
import { workService } from '@/services/workService';
import { assetService } from '@/services/assetService';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { Dragger } = Upload;

// 场景类型定义
interface Scene {
  id: number;
  title: string;
  description: string;
  location: string;
  timeOfDay: string;
  characters: string[];
  content: string;
  order: number;
}

// 角色类型定义
interface Character {
  id: number;
  name: string;
  description: string;
  age: number;
  gender: string;
  role: string;
}

// 集数类型定义
interface Episode {
  id: string;
  title: string;
  number: number;
  scenes: Scene[];
  characters: Character[];
  description?: string;
}

// 生成状态
type GenerationStatus = 'idle' | 'generating' | 'completed' | 'failed';

/** Convert flat storyboard array from script-service into grouped episode format for Storyboard page. */
function normalizeStoryboard(rawShots: any[] | undefined): any | null {
  if (!rawShots || !Array.isArray(rawShots) || rawShots.length === 0) return null;

  const MOVEMENT_TO_ANGLE: Record<string, string> = {
    '推': '正面平视', '拉': '正面平视', '摇': '摇镜头',
    '移': '跟踪拍摄', '跟': '跟踪拍摄', '升': '仰视',
    '降': '俯视', '固定': '正面平视',
  };
  const CN_NUMS: Record<string, number> = {
    '一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
  };

  const epMap = new Map<number, any[]>();
  for (const s of rawShots) {
    let epNum = s._episode || s.episode_number || 1;
    if (typeof epNum === 'string') epNum = CN_NUMS[epNum] || parseInt(epNum) || 1;

    if (!epMap.has(epNum)) epMap.set(epNum, []);
    epMap.get(epNum)!.push({
      id: s.shot_number || epMap.get(epNum)!.length + 1,
      number: s.shot_number || epMap.get(epNum)!.length + 1,
      shotType: s.camera_type || '中景',
      duration: s.duration_seconds || 5,
      cameraAngle: MOVEMENT_TO_ANGLE[s.camera_movement] || '正面平视',
      description: s.description || '',
      dialogue: '',
      characters: [],
      sceneRef: '',
      soundEffects: [] as string[],
      music: '',
      notes: '',
    });
  }

  const episodes = Array.from(epMap.entries())
    .sort(([a], [b]) => a - b)
    .map(([num, shots]) => ({
      id: `ep-${num}`,
      title: `第${num}集`,
      number: num,
      shots,
    }));

  return { episodes, generatedAt: new Date().toISOString() };
}

const Script: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // ============ 上传相关状态 ============
  const [inputTab, setInputTab] = useState<string>('novel');
  const [generationStatus, setGenerationStatus] = useState<GenerationStatus>('idle');
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generatedScriptTitle, setGeneratedScriptTitle] = useState<string>('');
  const [scriptId, setScriptId] = useState<number | null>(null);
  const [savingScript, setSavingScript] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const workCreatedRef = useRef(false); // 防止 StrictMode 重复创建作品

  // 表单值
  const [formTitle, setFormTitle] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formTheme, setFormTheme] = useState('成长');
  const [formStyle, setFormStyle] = useState('浪漫喜剧');
  const [formLength, setFormLength] = useState('短篇');
  const [formSetting, setFormSetting] = useState('现代都市');
  const [targetLocale, setTargetLocale] = useState('zh-CN');
  const [multiVersion, setMultiVersion] = useState(false);
  // 模板库
  const [templates, setTemplates] = useState<Array<{template_id:string;genre:string;genre_cn:string;description:string;total_episodes:number}>>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  useEffect(() => {
    setTemplatesLoading(true);
    fetch('/api/v1/scripts/templates')
      .then(r => r.json())
      .then(d => { if (d?.data) setTemplates(d.data); })
      .catch(() => {})
      .finally(() => setTemplatesLoading(false));
  }, []);

  // Multi-version result state
  const [multiVersions, setMultiVersions] = useState<any[]>([])
  const [multiWinner, setMultiWinner] = useState<any>(null)
  const [multiComparison, setMultiComparison] = useState<any>(null)
  const [versionModalOpen, setVersionModalOpen] = useState(false)
  const [selectedVersion, setSelectedVersion] = useState<string>('')

  // Intent mining state
  const [intentModalOpen, setIntentModalOpen] = useState(false)
  const [intentQuestions, setIntentQuestions] = useState<Array<{id:string;question:string;options:string[]}>>([])
  const [intentAnswers, setIntentAnswers] = useState<Record<string,string>>({})
  const [intentMining, setIntentMining] = useState(false)
  const [intentDetected, setIntentDetected] = useState<{genre:string;style:string;length:string} | null>(null)

  // Template match state
  const [matchedTemplate, setMatchedTemplate] = useState<any>(null)

  // Refs to bridge scope between generation branches and save logic
  const latestResultRef = useRef<any>(null)
  const latestEpisodesRef = useRef<Episode[]>([])

  // ============ 分集剧本编辑状态 ============
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  // 去重：防止 React 严格模式或其他原因导致的重复渲染
  const uniqueEpisodes = useMemo(() => {
    const seen = new Set<string>();
    return episodes.filter(ep => {
      if (seen.has(ep.id)) return false;
      seen.add(ep.id);
      return true;
    });
  }, [episodes]);
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('');
  const [activeTab, setActiveTab] = useState('scenes');
  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [isSceneModalOpen, setIsSceneModalOpen] = useState(false);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  // ============ 持久化 key（user-namespaced）============
  const { saveState: persistState, loadState: loadPersisted, loadCached, restoreFromBackend, getWorkId, setWorkId, userId } = usePipelinePersistence();
  // ============ 初始化：恢复上次的状态 ============
  useEffect(() => {
    const initLoad = async () => {
      const urlWorkId = searchParams.get('workId');
      let saved: any = null;

      if (urlWorkId && urlWorkId !== 'default') {
        // Save workId to localStorage so other pages can find it
        setWorkId(urlWorkId);
        // Restore all pipeline steps from backend into cache
        try {
          await restoreFromBackend(urlWorkId);
          saved = loadCached('script');
        } catch {}
      } else {
        // No workId — try to restore from localStorage cache
      }

      // Fallback to localStorage if backend fetch didn't produce data
      if (!saved) {
        saved = await loadPersisted('script');
      }

      if (saved) {
        // Infer completed state from data presence (old pipeline data lacks generationStatus)
        const isCompleted = saved.generationStatus === 'completed' || saved.episodes?.length > 0 || saved.content;
        if (isCompleted) {
          if (!saved.generationStatus) saved.generationStatus = 'completed';
          // Has full data: load immediately, map API format to frontend Episode type
          if (saved.episodes?.length > 0) {
            setGeneratedScriptTitle(saved.generatedScriptTitle || saved.title || '');
            setGenerationStatus('completed');
            setGenerationProgress(100);
            if (saved.scriptId) setScriptId(saved.scriptId);
            const mapped = saved.episodes.map((ep: any, i: number) => ({
              id: ep.id || `ep-${i + 1}-${Date.now().toString(36)}`,
              title: ep.title || `第${i + 1}集`,
              number: ep.episode_number || ep.number || (i + 1),
              description: ep.content || ep.description || '',
              scenes: ep.scenes || [], characters: ep.characters || [],
            }));
            setEpisodes(mapped);
            if (mapped.length > 0) setActiveEpisodeId(mapped[0].id);
          } else if (saved.content) {
            if (saved.scriptId) setScriptId(saved.scriptId);
            parseScriptToEpisodes(saved.content, saved.generatedScriptTitle || '');
          } else if (saved.scriptId) {
            // Set completion state immediately so editor shows
            setGeneratedScriptTitle(saved.generatedScriptTitle || '');
            setGenerationStatus('completed');
            setGenerationProgress(100);
            if (saved.scriptId) setScriptId(saved.scriptId);
            // Fetch full script content asynchronously
            scriptService.getScript(String(saved.scriptId)).then((resp: any) => {
              const s = resp?.data?.script || resp?.script || resp?.data || resp;
              if (s?.content) parseScriptToEpisodes(s.content, s.title || '');
              if (s?.episodes?.length > 0) {
                const mapped = s.episodes.map((ep: any, i: number) => ({
                  id: `ep-${i + 1}-${Date.now().toString(36)}`,
                  title: ep.title || `第${i + 1}集`,
                  number: ep.episode_number || (i + 1),
                  description: ep.content || ep.description || '',
                  scenes: [], characters: [],
                }));
                setEpisodes(mapped);
                if (mapped.length > 0) setActiveEpisodeId(mapped[0].id);
              }
            }).catch(() => {});
          }
        } else if (saved.generationStatus === 'generating' && saved.taskId) {
          scriptService.getGenerationStatus(saved.taskId).then((status) => {
            if (status && status.status !== 'failed') {
              setGenerationStatus('generating');
              setGenerationProgress(saved.generationProgress || 0);
              setGeneratedScriptTitle(saved.generatedScriptTitle || '');
              pollGenerationStatus(saved.taskId);
            } else {
            }
          }).catch(() => {
          });
        } else {
        }
      }
    };
    initLoad();
  }, [searchParams]);

  // ============ 轮询逻辑 ============
  const pollGenerationStatus = useCallback((id: string) => {
    let retry404 = 0;
    pollingRef.current = setInterval(async () => {
      try {
        retry404 = 0; // Reset on success
        const status = await scriptService.getGenerationStatus(id);
        if (status) {
          setGenerationProgress(status.progress || 0);

          if (status.status === 'completed') {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setGenerationStatus('completed');
            setGenerationProgress(100);
            const completedScriptId = (status as any).script_id;
            if (completedScriptId) setScriptId(completedScriptId);
            message.success('剧本生成完成！');

            // 立即持久化 scriptId，不等 setTimeout（防止 workId 创建失败导致 scriptId 丢失）
            persistState('script', {
              scriptId: completedScriptId,
              generationStatus: 'completed',
              generationProgress: 100,
              taskId: id,
              generatedScriptTitle: formTitle,
            });

            const resultEpisodes: any[] = [];
            let resultStoryboard: any = null;
            const title = status.result?.title || generatedScriptTitle || formTitle;
            const content = status.result?.content || '';

            const resultData: any = status.result || status;
            if (resultData) {
              setGeneratedScriptTitle(resultData.title || formTitle);
              // Capture V2 storyboard data for smart storyboard
              if (resultData.storyboard) {
                resultStoryboard = resultData.storyboard;
              }
              if (resultData.episodes && resultData.episodes.length > 0) {
                const backendEpisodes: Episode[] = resultData.episodes.map((ep: any) => ({
                  id: `ep-${ep.episode_number || ep.episodeNumber || 1}-${Date.now().toString(36)}`,
                  title: ep.title || `第${ep.episode_number || 1}集`,
                  number: ep.episode_number || ep.episodeNumber || 1,
                  scenes: [], characters: [],
                  description: ep.content || '',
                }));
                setEpisodes(backendEpisodes);
                resultEpisodes.push(...JSON.parse(JSON.stringify(backendEpisodes)));
                if (backendEpisodes.length > 0) setActiveEpisodeId(backendEpisodes[0].id);
              } else {
                parseScriptToEpisodes(resultData.content || '', resultData.title || formTitle);
              }
            } else {
              setGeneratedScriptTitle(formTitle);
              createDefaultEpisodes(formTitle);
            }

            // 自动保存（使用捕获的 episodes + content 双保险）
            const epsForSave = resultEpisodes;
            const contentForSave = content;
            setTimeout(async () => {
              let workId = getWorkId();
              if (!workId && !workCreatedRef.current) {
                workCreatedRef.current = true;
                try {
                  const resp = await fetch('/api/v1/works', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title, type: '短剧', description: '', userId: 'anonymous' }),
                  });
                  if (resp.ok) { const w = await resp.json(); if (w?.id) { setWorkId(w.id); workId = w.id; } }
                } catch {}
              }
              if (workId) {
                try {
                  // Save via hook (backend-first with cache sync)
                  await persistState('script', {
                    scriptId: (status as any).script_id,
                    title: title,
                    episodeCount: epsForSave.length,
                    generatedScriptTitle: title,
                    generationStatus: 'completed',
                    generationProgress: 100,
                    episodes: epsForSave,
                    content: contentForSave,
                  } as any, workId);
                  if (resultStoryboard) {
                    const normalized = normalizeStoryboard(resultStoryboard);
                    if (normalized) {
                      await persistState('storyboard', normalized, workId);
                    }
                  }
                } catch {}
              }
            }, 100);
          } else if (status.status === 'failed') {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setGenerationStatus('failed');
            setGenerationError(status.error || status.error_message || '剧本生成失败，请重试');
            message.error(status.error || status.error_message || '剧本生成失败，请重试');
            persistState('script', { generationStatus: 'failed' });
          } else {
            // 仍在生成中：持久化进度以便页面刷新后恢复
            persistState('script', {
              generationStatus: 'generating',
              generationProgress: status.progress || 0,
              taskId: id,
              generatedScriptTitle: formTitle,
            });
          }
        }
      } catch (err: any) {
        // 404 = 任务可能还未持久化，重试几次再放弃
        if (err?.response?.status === 404) {
          retry404 = (retry404 || 0) + 1;
          if (retry404 > 20) {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setGenerationStatus('idle');
            console.log('任务已过期，已停止轮询');
          }
        } else {
          console.error('轮询状态失败:', err?.message || err);
        }
      }
    }, 3000);
  }, [formTitle]);

  // 清理轮询
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // ============ 解析剧本内容为分集 ============
  const parseScriptToEpisodes = (content: string, title: string) => {
    const episodes: Episode[] = [];
    const episodePattern = /(?:第\s*([一二三四五六七八九十百千万\d]+)\s*集|Episode\s+(\d+))/gi;
    const parts = content.split(episodePattern);

    if (parts.length <= 1) {
      episodes.push({
        id: 'ep-1',
        title: title || '完整剧本',
        number: 1,
        scenes: [],
        characters: [],
        description: content,
      });
    } else {
      let epIndex = 0;
      let currentEpContent = '';
      let currentEpTitle = '';
      let epNumber = 1;

      for (let i = 0; i < parts.length; i++) {
        const part = parts[i]?.trim();
        if (!part) continue;

        const epMatch = part.match(/^[一二三四五六七八九十百千万\d]+$/);
        if (epMatch && i + 1 < parts.length) {
          if (currentEpContent) {
            episodes.push({
              id: `ep-${epIndex + 1}`,
              title: currentEpTitle || `第${epNumber}集`,
              number: epNumber,
              scenes: [],
              characters: [],
              description: currentEpContent.trim(),
            });
            epIndex++;
          }
          epNumber = epIndex + 1;
          currentEpTitle = `第${part}集`;
          currentEpContent = '';
        } else if (part) {
          currentEpContent += part + '\n';
        }
      }

      if (currentEpContent) {
        episodes.push({
          id: `ep-${epIndex + 1}`,
          title: currentEpTitle || `第${epNumber}集`,
          number: epNumber,
          scenes: [],
          characters: [],
          description: currentEpContent.trim(),
        });
      }
    }

    setEpisodes(episodes);
    if (episodes.length > 0) {
      setActiveEpisodeId(episodes[0].id);
    }
  };

  const createDefaultEpisodes = (title: string) => {
    const defaultEpisode: Episode = {
      id: 'ep-1',
      title: title || '第一集',
      number: 1,
      scenes: [],
      characters: [],
      description: '剧本内容将在此展示',
    };
    setEpisodes([defaultEpisode]);
    setActiveEpisodeId(defaultEpisode.id);
  };

  // ============ 生成剧本 ============
  const handleGenerate = async () => {
    if (!formTitle.trim()) {
      message.warning('请输入剧本标题');
      return;
    }
    if (!formContent.trim()) {
      message.warning('请输入内容');
      return;
    }

    setGenerationStatus('generating');
    setGenerationProgress(0);
    setGenerationError(null);
    workCreatedRef.current = false;  // 重置防止重复创建的标记

    try {
      let response;

      if (inputTab === 'novel') {
        response = await scriptService.generateScriptFromNovel({
          title: formTitle,
          novel_content: formContent,
          theme: formTheme,
          length: formLength,
          style: formStyle,
          setting: formSetting,
          user_id: String(userId || 'anonymous'),
        });
      } else if (inputTab === 'idea') {
        // ── Step 0: Intent Mining (conversational guidance) ──
        let enrichedOutline = formContent;
        if (!multiVersion) {
          try {
            setGenerationProgress(5);
            const intentResult = await scriptService.mineIntent({
              idea: formContent, style: formStyle, theme: formTheme, length: formLength,
            });
            if (intentResult.questions && intentResult.questions.length > 0) {
              // Show conversational guidance modal
              setIntentQuestions(intentResult.questions);
              setIntentAnswers({});
              setIntentDetected({
                genre: intentResult.detected_genre,
                style: intentResult.suggested_style || formStyle,
                length: intentResult.suggested_length || formLength,
              });
              setIntentModalOpen(true);
              setGenerationStatus('idle');
              setGenerationProgress(0);
              return; // Pause — user answers questions, then generation continues from handleIntentConfirm
            }
            if (intentResult.enriched_outline) {
              enrichedOutline = intentResult.enriched_outline;
              if (intentResult.suggested_style && !formStyle) setFormStyle(intentResult.suggested_style);
              message.success('已自动分析您的想法，开始生成...');
            }
          } catch { /* Intent mining failed — proceed with raw outline */ }
        }

        // Match plot template
        try {
          const tmpl = await scriptService.matchPlotTemplate(formStyle, formTheme)
          if ((tmpl as any)?.data?.matched) setMatchedTemplate((tmpl as any).data)
        } catch {}

        if (multiVersion) {
          // Multi-version generation
          setGenerationProgress(30);
          const result = await scriptService.generateMultiVersion({
            title: formTitle, outline: enrichedOutline,
            theme: formTheme, length: formLength,
            style: formStyle, setting: formSetting,
            user_id: String(userId || 'anonymous'),
          });
          setGenerationProgress(100);
          const data = (result as any)?.data
          if (data?.versions) {
            setMultiVersions(data.versions)
            setMultiWinner(data.winner)
            setMultiComparison(data.comparison)
            setSelectedVersion(data.winner?.version || data.versions[0]?.version || '')
            setVersionModalOpen(true)
            // Load winner's episodes by default
            const winnerVer = data.versions.find((v: any) => v.version === data.winner?.version) || data.versions[0]
            if (winnerVer?.episodes) {
              setGeneratedScriptTitle(formTitle)
              const parsedEpisodes: Episode[] = winnerVer.episodes.map((ep: any) => ({
                id: `ep-${ep.episode_number || 1}-${Date.now().toString(36)}`,
                title: ep.title || `第${ep.episode_number || 1}集`,
                number: ep.episode_number || 1,
                scenes: [], characters: [],
                description: ep.content || '',
              }))
              setEpisodes(parsedEpisodes)
              if (parsedEpisodes.length > 0) setActiveEpisodeId(parsedEpisodes[0].id)
              latestEpisodesRef.current = parsedEpisodes
              latestResultRef.current = { title: formTitle }
            }
          }
          setGenerationStatus('completed')
        } else {
          // Async outline — submit task_id, poll for results
          setGenerationProgress(10);
          const resp = await scriptService.generateScriptFromOutline({
            title: formTitle, outline: enrichedOutline,
            theme: formTheme, length: formLength,
            style: formStyle, setting: formSetting,
            user_id: String(userId || 'anonymous'),
          });
          if (resp?.task_id) {
            persistState('script', { generationStatus: 'generating', generationProgress: 10, taskId: resp.task_id, generatedScriptTitle: formTitle });
            pollGenerationStatus(resp.task_id);
            return;
          }
          throw new Error('未获取到任务ID');
        }

        // 保存到 localStorage 和后端
        const scriptData = {
          episodes: JSON.parse(JSON.stringify(latestEpisodesRef.current)),
          generatedScriptTitle: latestResultRef.current.title,
          generationStatus: 'completed', generationProgress: 100,
        };
        // 创建作品并直接保存到后端
        let wId = getWorkId();
        if (!wId) {
          try {
            // 绕过 axios，直接 fetch（避免可能的 interceptor/序列化问题）
            const resp = await fetch('/api/v1/works', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ title: latestResultRef.current.title, type: '短剧', description: '', userId: 'anonymous' }),
            });
            if (resp.ok) {
              const work = await resp.json();
              if (work?.id) { setWorkId(work.id); wId = work.id; }
            } else {
              console.error('Create work returned:', resp.status, await resp.text());
            }
          } catch (e) { console.error('Create work failed:', e); }
        }
        if (wId) {
          try {
            await persistState('script', scriptData, wId);
            // Save V2 storyboard data so "智能分镜" can skip storyboard-service
            if ((latestResultRef.current as any).storyboard) {
              const normalized = normalizeStoryboard((latestResultRef.current as any).storyboard);
              if (normalized) {
                await persistState('storyboard', normalized, wId);
              }
            }
          } catch (e) { console.error('Pipeline save failed:', e); message.warning('剧本保存失败，请勿刷新页面'); }
        } else {
          message.warning('作品创建失败，请重试');
        }

        message.success(`剧本生成完成，共 ${latestResultRef.current.total_episodes} 集`);
        return;
      }

      if ((response as any)?.task_id) {
        const id = (response as any).task_id;
        setGenerationProgress(10);
        persistState('script', { generationStatus: 'generating', generationProgress: 10, taskId: id, generatedScriptTitle: formTitle });
        message.info('剧本生成任务已提交，正在生成中...');
        pollGenerationStatus(id);
      } else {
        throw new Error('未获取到任务ID');
      }
    } catch (err: any) {
      setGenerationStatus('failed');
      const detail = err?.response?.data?.detail;
      const errMsg = Array.isArray(detail) ? detail.map((e: any) => e.msg || '').join('; ') : (detail || err?.message || '生成请求失败');
      setGenerationError(errMsg);
      message.error('生成请求失败，请重试');
    }
  };

  // ============ 上传并分集（上传完整剧本，后端按集拆分） ============
  // ============ 对话式引导确认 ============
  const handleIntentConfirm = async () => {
    setIntentModalOpen(false);
    setGenerationStatus('generating');
    setGenerationProgress(10);
    setGenerationError(null);

    try {
      // Step 1: Get enriched outline with user's answers
      const intentResult = await scriptService.mineIntent({
        idea: formContent,
        style: formStyle, theme: formTheme, length: formLength,
        answers: intentAnswers,
      });

      const enrichedOutline = intentResult.enriched_outline || formContent;
      if (intentResult.suggested_style) setFormStyle(intentResult.suggested_style);

      // Step 2: Generate with enriched outline
      setGenerationProgress(30);
      const result = await scriptService.generateScriptFromOutlineSync({
        title: formTitle, outline: enrichedOutline,
        theme: formTheme, length: formLength,
        style: intentResult.suggested_style || formStyle,
        setting: formSetting,
        user_id: String(userId || 'anonymous'),
        target_locale: targetLocale,
      });

      setGenerationProgress(100);
      setGeneratedScriptTitle(result.title);
      const parsedEpisodes: Episode[] = result.episodes.map((ep: any) => ({
        id: `ep-${ep.episode_number || 1}-${Date.now().toString(36)}`,
        title: ep.title || `第${ep.episode_number || 1}集`,
        number: ep.episode_number || 1,
        scenes: [], characters: [],
        description: ep.content || '',
      }));
      setEpisodes(parsedEpisodes);
      setGenerationStatus('completed');
      if (parsedEpisodes.length > 0) setActiveEpisodeId(parsedEpisodes[0].id);
      latestEpisodesRef.current = parsedEpisodes;
      latestResultRef.current = result;
      message.success(`已根据您的偏好生成 ${result.total_episodes} 集剧本`);
    } catch (err: any) {
      setGenerationStatus('failed');
      setGenerationError(err?.message || '生成失败');
    }
  };

  const handleUploadAndSplit = async () => {
    if (!formTitle.trim()) {
      message.warning('请输入剧本标题');
      return;
    }
    if (!formContent.trim()) {
      message.warning('请输入剧本内容');
      return;
    }

    setGenerationStatus('generating');
    setGenerationProgress(0);
    setGenerationError(null);

    try {
      const result = await scriptService.uploadAndSplitScript({
        title: formTitle,
        content: formContent,
      });

      // 将后端 EpisodeItem[] 映射为前端 Episode[]
      const eps: Episode[] = latestResultRef.current.episodes.map((ep: any) => ({
        id: `ep-${ep.episode_number}-${Date.now().toString(36)}`,
        title: ep.title,
        number: ep.episode_number,
        scenes: [],
        characters: [],
        description: ep.content,
      }));

      setScriptId(latestResultRef.current.script_id);
      setEpisodes(eps);
      setGeneratedScriptTitle(latestResultRef.current.title);
      setGenerationStatus('completed');
      setGenerationProgress(100);

      // 立即创建作品并保存到后端
      const scriptData = {
        episodes: JSON.parse(JSON.stringify(latestEpisodesRef.current)),
        generatedScriptTitle: latestResultRef.current.title,
        generationStatus: 'completed',
        generationProgress: 100,
        scriptId: latestResultRef.current.script_id,
      };
      let wId = getWorkId();
      if (!wId) {
        try {
          const work = await workService.createWork({
            title: latestResultRef.current.title,
            type: '短剧',
            description: '',
            userId: userId,
          });
          if (work?.id) {
            setWorkId(work.id);
            wId = work.id;
          }
        } catch {}
      }
      await persistState('script', scriptData, wId || undefined);

      message.success(`剧本上传成功，已拆分为 ${result.total_episodes} 集`);
    } catch (err: any) {
      setGenerationStatus('failed');
      const errMsg = err?.response?.data?.detail || err?.message || '上传失败';
      setGenerationError(errMsg);
      message.error(errMsg);
    }
  };

  // 自动保存：当生成完成且 episodes 有数据时保存
  useEffect(() => {
    if (generationStatus === 'completed' && uniqueEpisodes.length > 0) {
      const scriptData = {
        episodes: JSON.parse(JSON.stringify(episodes)),
        generatedScriptTitle,
        generationStatus,
        generationProgress,
      };
      // 仅保存到已有 workId，不创建新作品（创建由 handleUploadAndSplit/handleGenerate 负责）
      const workId = getWorkId();
      if (workId && workId.startsWith('wk_')) {
        persistState('script', scriptData, workId);
      } else {
        persistState('script', scriptData);
      }
    }
  }, [episodes, generationStatus, generatedScriptTitle, generationProgress]);

  // 返回上传视图
  const handleBackToUpload = () => {
    setGenerationStatus('idle');
    setGenerationProgress(0);
    setGenerationError(null);
    setEpisodes([]);
    setActiveEpisodeId('');
    setScriptId(null);
  };

  // ============ 集数操作 ============
  const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);
  const currentScenes = currentEpisode?.scenes || [];
  const currentCharacters = currentEpisode?.characters || [];

  const handleAddEpisode = () => {
    const newEpisode: Episode = {
      id: `ep-${Date.now()}`,
      title: `第${uniqueEpisodes.length + 1}集`,
      number: uniqueEpisodes.length + 1,
      scenes: [],
      characters: [],
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

  /** 保存剧本：将当前 episodes（含编辑后的内容）持久化到后端 + localStorage */
  const handleSaveScript = useCallback(async () => {
    if (!scriptId) { message.warning('请先生成剧本'); return; }
    setSavingScript(true);
    try {
      // 序列化 episodes：去掉本地临时字段，映射到后端 EpisodeUpdateItem 格式
      const episodesData = uniqueEpisodes.map(ep => ({
        episode_number: ep.number,
        title: ep.title,
        content: ep.description || '',
        scenes: ep.scenes.map(s => ({
          id: s.id, title: s.title, description: s.description,
          location: s.location, timeOfDay: s.timeOfDay,
          characters: s.characters, content: s.content, order: s.order,
        })),
        characters: ep.characters.map(c => ({
          id: c.id, name: c.name, description: c.description,
          age: c.age, gender: c.gender, role: c.role,
        })),
      }));

      // 保存到后端
      await scriptService.updateScript(String(scriptId), {
        title: generatedScriptTitle,
        episodes: episodesData,
      });

      // 同步保存到后端（使用 hook 的 persistState，支持 backend pipeline sync）
      persistState('script', { title: generatedScriptTitle, episodes: episodes, scriptId }, getWorkId() || undefined);

      message.success('剧本已保存');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '保存失败');
    }
    setSavingScript(false);
  }, [scriptId, uniqueEpisodes, episodes, generatedScriptTitle, getWorkId, persistState]);

  /** 更新当前剧集 description（中间文本编辑区） */
  const handleEpisodeContentChange = useCallback((newContent: string) => {
    if (!currentEpisode) return;
    setEpisodes(prev => prev.map(ep =>
      ep.id === currentEpisode.id ? { ...ep, description: newContent } : ep
    ));
  }, [currentEpisode]);

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

  // ============ 场景操作 ============
  const updateEpisodeScenes = (scenes: Scene[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, scenes } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  const handleAddScene = () => {
    const newScene: Scene = {
      id: Date.now(),
      title: '新场景',
      description: '',
      location: '',
      timeOfDay: '白天',
      characters: [],
      content: '',
      order: currentScenes.length + 1,
    };
    setEditingScene(newScene);
    setIsSceneModalOpen(true);
  };

  const handleEditScene = (scene: Scene) => {
    setEditingScene(scene);
    setIsSceneModalOpen(true);
  };

  const handleDeleteScene = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个场景吗？',
      onOk: () => {
        const updatedScenes = currentScenes.filter(scene => scene.id !== id);
        updateEpisodeScenes(updatedScenes);
        message.success('场景已删除');
      },
    });
  };

  const handleSaveScene = (values: any) => {
    if (editingScene) {
      const updatedScene = { ...editingScene, ...values };
      let updatedScenes: Scene[];

      const exists = currentScenes.find(s => s.id === updatedScene.id);
      if (exists) {
        updatedScenes = currentScenes.map(scene =>
          scene.id === updatedScene.id ? updatedScene : scene
        );
      } else {
        updatedScenes = [...currentScenes, updatedScene];
      }

      updateEpisodeScenes(updatedScenes);
      setIsSceneModalOpen(false);
      setEditingScene(null);
    }
  };

  // ============ 角色操作 ============
  const updateEpisodeCharacters = (characters: Character[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, characters } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  const handleAddCharacter = () => {
    const newCharacter: Character = {
      id: Date.now(),
      name: '新角色',
      description: '',
      age: 25,
      gender: '男',
      role: '配角',
    };
    setEditingCharacter(newCharacter);
    setIsCharacterModalOpen(true);
  };

  const handleEditCharacter = (character: Character) => {
    setEditingCharacter(character);
    setIsCharacterModalOpen(true);
  };

  const handleDeleteCharacter = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个角色吗？',
      onOk: () => {
        const updatedCharacters = currentCharacters.filter(char => char.id !== id);
        updateEpisodeCharacters(updatedCharacters);
        message.success('角色已删除');
      },
    });
  };

  const handleSaveCharacter = (values: any) => {
    if (editingCharacter) {
      const updatedCharacter = { ...editingCharacter, ...values };
      let updatedCharacters: Character[];

      const exists = currentCharacters.find(c => c.id === updatedCharacter.id);
      if (exists) {
        updatedCharacters = currentCharacters.map(char =>
          char.id === updatedCharacter.id ? updatedCharacter : char
        );
      } else {
        updatedCharacters = [...currentCharacters, updatedCharacter];
      }

      updateEpisodeCharacters(updatedCharacters);
      setIsCharacterModalOpen(false);
      setEditingCharacter(null);
    }
  };

  // ============ 文件上传处理 ============
  const handleFileUpload = async (file: File): Promise<boolean> => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    try {
      if (ext === 'docx' || ext === 'doc') {
        const mammoth = await import('mammoth');
        const arrayBuffer = await file.arrayBuffer();
        const result = await mammoth.extractRawText({ arrayBuffer });
        setFormContent(result.value);
        message.success(`已加载Word文件: ${file.name}`);
      } else if (ext === 'pdf') {
        const pdfjsLib = await import('pdfjs-dist');
        pdfjsLib.GlobalWorkerOptions.workerSrc = '';
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        const texts: string[] = [];
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const content = await page.getTextContent();
          texts.push(content.items.map((item: any) => item.str).join(' '));
        }
        setFormContent(texts.join('\n\n'));
        message.success(`已加载PDF文件: ${file.name}`);
      } else {
        const reader = new FileReader();
        reader.onload = (e) => {
          setFormContent(e.target?.result as string);
          message.success(`已加载文件: ${file.name}`);
        };
        reader.onerror = () => message.error('文件读取失败');
        reader.readAsText(file);
      }
    } catch {
      message.error('文件解析失败，请确认文件格式正确');
    }
    return false;
  };

  // ============ 渲染：上传视图 ============
  const applyTemplate = (t: typeof templates[0]) => {
    setFormTitle(t.genre_cn + ' — ' + t.description.slice(0, 30));
    setFormContent(`【${t.genre_cn}】${t.description}\n\n共${t.total_episodes}集\n\n请基于上述信息生成完整剧本，包含角色设定、分集大纲和每集钩子。`);
    setFormStyle(t.genre_cn);
    message.success(`已套用「${t.genre_cn}」模板`);
  };

  const renderUploadForm = () => (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 0' }}>
      <Form layout="vertical" size="large">
        <Form.Item
          label="剧本标题"
          required
          rules={[{ required: true, message: '请输入剧本标题' }]}
        >
          <Input
            placeholder="给你的剧本起个名字..."
            value={formTitle}
            onChange={(e) => setFormTitle(e.target.value)}
            prefix={<FileTextOutlined style={{ color: '#d2d2d7' }} />}
          />
        </Form.Item>

        {/* 模板画廊 — 仅想法/大纲Tab显示 */}
        {inputTab === 'idea' && (
          <div style={{ marginBottom: 16 }}>
            <Text style={{ fontSize: 12, color: '#6b7280', marginBottom: 8, display: 'block' }}>
              🎬 行业验证的剧本模板 — 点击即可套用
            </Text>
            <Spin spinning={templatesLoading}>
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                {templates.map(t => (
                  <div key={t.template_id} onClick={() => applyTemplate(t)}
                    style={{ cursor: 'pointer', flexShrink: 0, width: 160, padding: 10, borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', transition: 'box-shadow 0.15s' }}
                    onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'}
                    onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}>
                    <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>{t.genre_cn}</Text>
                    <Text style={{ fontSize: 11, color: '#6b7280', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.description}</Text>
                    <Tag style={{ marginTop: 6, fontSize: 10 }}>{t.total_episodes}集模板</Tag>
                  </div>
                ))}
                {!templatesLoading && templates.length === 0 && (
                  <Text style={{ color: '#9ca3af', fontSize: 12 }}>加载中...</Text>
                )}
              </div>
            </Spin>
          </div>
        )}

        <Form.Item
          label={
            <span>
              {inputTab === 'novel' ? '小说内容' : inputTab === 'script' ? '剧本内容' : '想法/大纲'}
            </span>
          }
          required
        >
          <TextArea
            placeholder={
              inputTab === 'novel'
                ? '在此粘贴您的小说内容，或使用下方的文件上传功能...'
                : inputTab === 'script'
                ? '在此粘贴剧本内容，或直接拖拽文件到下方上传区（上传后自动分集）...'
                : '在此描述您的创意想法或剧本大纲...'
            }
            rows={12}
            value={formContent}
            onChange={(e) => setFormContent(e.target.value)}
            style={{ fontSize: 14 }}
          />
        </Form.Item>

        {(inputTab === 'novel' || inputTab === 'script') && (
          <Form.Item label={inputTab === 'novel' ? '上传小说文件' : '上传剧本文件'}>
            <Dragger
              accept={inputTab === 'novel' ? '.txt,.md,.doc,.docx,.pdf' : '.txt,.md,.doc,.docx'}
              multiple={false}
              maxCount={1}
              {...(inputTab === 'script'
                ? {
                    // 剧本模式: 直接上传到后端, 自动分集
                    customRequest: async (options: any) => {
                      const { file, onSuccess, onError } = options
                      try {
                        const result = await scriptService.uploadScriptFile(file as File, formTitle || '未命名剧本')
                        const parsedEpisodes: Episode[] = result.episodes.map((ep: any) => ({
                          id: `ep-${ep.episode_number}-${Date.now().toString(36)}`,
                          title: ep.title,
                          number: ep.episode_number,
                          scenes: [],
                          characters: [],
                          description: ep.content || '',
                        }))
                        setScriptId(result.script_id)
                        setEpisodes(parsedEpisodes)
                        setGeneratedScriptTitle(result.title)
                        setGenerationStatus('completed')
                        setGenerationProgress(100)
                        setFormContent('')  // 清空 TextArea
                        message.success(`剧本上传成功，已拆分为 ${result.total_episodes} 集`)
                        onSuccess(result, file)
                      } catch (err: any) {
                        const msg = err?.response?.data?.detail || err?.message || '上传失败'
                        message.error(msg)
                        onError(err)
                      }
                    },
                    showUploadList: false,
                  }
                : {
                    // 小说/想法模式: 客户端读取, 填入 TextArea
                    beforeUpload: handleFileUpload,
                  }
              )}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                {inputTab === 'script'
                  ? '支持 .txt, .md, .docx 文件，上传后自动分集'
                  : `支持 ${inputTab === 'novel' ? '.txt, .md, .doc, .docx, .pdf' : '.txt, .md, .doc, .docx'} 文件`}
              </p>
            </Dragger>
          </Form.Item>
        )}

        {inputTab !== 'script' && (
          <>
            <Row gutter={24}>
          <Col span={8}>
            <Form.Item label="剧本主题" tooltip="选择预设主题或自行输入">
              <Select
                value={formTheme}
                onChange={setFormTheme}
                showSearch
                allowClear
                placeholder="选择或输入主题..."
                filterOption={(input, option) =>
                  (option?.label as string)?.includes(input) ||
                  (option?.value as string)?.includes(input)
                }
                options={[
                  { label: '🏙️ 都市', value: '都市', options: [
                    { label: '都市情感', value: '都市情感' },
                    { label: '都市逆袭', value: '都市逆袭' },
                    { label: '商战职场', value: '商战职场' },
                    { label: '校园青春', value: '校园青春' },
                    { label: '家庭伦理', value: '家庭伦理' },
                  ]},
                  { label: '💕 言情', value: '言情', options: [
                    { label: '甜宠', value: '甜宠' },
                    { label: '虐恋', value: '虐恋' },
                    { label: '先婚后爱', value: '先婚后爱' },
                    { label: '破镜重圆', value: '破镜重圆' },
                    { label: '暗恋成真', value: '暗恋成真' },
                  ]},
                  { label: '⚔️ 古风', value: '古风', options: [
                    { label: '宫斗宅斗', value: '宫斗宅斗' },
                    { label: '穿越重生', value: '穿越重生' },
                    { label: '武侠江湖', value: '武侠江湖' },
                    { label: '仙侠修真', value: '仙侠修真' },
                    { label: '权谋天下', value: '权谋天下' },
                  ]},
                  { label: '🔮 奇幻', value: '奇幻', options: [
                    { label: '玄幻魔法', value: '玄幻魔法' },
                    { label: '异世大陆', value: '异世大陆' },
                    { label: '系统流派', value: '系统流派' },
                    { label: '异能觉醒', value: '异能觉醒' },
                  ]},
                  { label: '🚀 科幻', value: '科幻', options: [
                    { label: '未来世界', value: '未来世界' },
                    { label: '末日废土', value: '末日废土' },
                    { label: '星际太空', value: '星际太空' },
                    { label: '人工智能', value: '人工智能' },
                  ]},
                  { label: '🔍 悬疑', value: '悬疑', options: [
                    { label: '刑侦推理', value: '刑侦推理' },
                    { label: '悬疑惊悚', value: '悬疑惊悚' },
                    { label: '谍战特工', value: '谍战特工' },
                    { label: '灵异鬼怪', value: '灵异鬼怪' },
                  ]},
                  { label: '💪 逆袭', value: '逆袭', options: [
                    { label: '重生复仇', value: '重生复仇' },
                    { label: '废柴逆袭', value: '废柴逆袭' },
                    { label: '赘婿翻身', value: '赘婿翻身' },
                    { label: '强者归来', value: '强者归来' },
                  ]},
                  { label: '🎭 其他', value: '其他', options: [
                    { label: '喜剧搞笑', value: '喜剧搞笑' },
                    { label: '热血竞技', value: '热血竞技' },
                    { label: '治愈温情', value: '治愈温情' },
                    { label: '架空历史', value: '架空历史' },
                    { label: '军事战争', value: '军事战争' },
                  ]},
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="剧本风格" tooltip="选择视觉和叙事风格">
              <Select
                value={formStyle}
                onChange={setFormStyle}
                showSearch
                allowClear
                placeholder="选择风格..."
                filterOption={(input, option) =>
                  (option?.label as string)?.includes(input) ||
                  (option?.value as string)?.includes(input)
                }
                options={[
                  { label: '🎬 主流风格', value: '主流', options: [
                    { label: '写实风格', value: '写实风格' },
                    { label: '浪漫喜剧', value: '浪漫喜剧' },
                    { label: '悬疑风格', value: '悬疑风格' },
                    { label: '科幻风格', value: '科幻风格' },
                    { label: '古装风格', value: '古装风格' },
                    { label: '都市风格', value: '都市风格' },
                  ]},
                  { label: '🎨 视觉风格', value: '视觉', options: [
                    { label: '电影级写实', value: '电影级写实' },
                    { label: '赛博朋克', value: '赛博朋克' },
                    { label: '日系清新', value: '日系清新' },
                    { label: '港风复古', value: '港风复古' },
                    { label: '民国风情', value: '民国风情' },
                    { label: '暗黑哥特', value: '暗黑哥特' },
                  ]},
                  { label: '📺 叙事风格', value: '叙事', options: [
                    { label: '快节奏爽文', value: '快节奏爽文' },
                    { label: '慢热细腻', value: '慢热细腻' },
                    { label: '轻喜剧', value: '轻喜剧' },
                    { label: '暗黑深沉', value: '暗黑深沉' },
                    { label: '纪实风格', value: '纪实风格' },
                  ]},
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="剧本长度" tooltip="参考红果短剧分类标准">
              <Select value={formLength} onChange={setFormLength}>
                <Option value="超短篇">超短篇（1-5集，每集1-2分钟）</Option>
                <Option value="短篇">短篇（6-15集，每集2-3分钟）</Option>
                <Option value="中篇">中篇（16-40集，每集3-5分钟）</Option>
                <Option value="长篇">长篇（41-80集，每集3-5分钟）</Option>
                <Option value="超长篇">超长篇（80-120集，每集2-5分钟）</Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>

        <Form.Item label="故事背景">
          <Input
            placeholder="例如：现代都市、古代宫廷、未来世界、末世废土..."
            value={formSetting}
            onChange={(e) => setFormSetting(e.target.value)}
          />
        </Form.Item>

        <Form.Item label="目标市场" tooltip="选择海外本土化市场，剧本将自动适配当地文化（角色原型、场景、叙事风格）">
          <Select value={targetLocale} onChange={setTargetLocale}>
            <Option value="zh-CN">🇨🇳 中国大陆（默认）</Option>
            <Option value="en-US">🇺🇸 北美 — Billionaire Romance / Mystery</Option>
            <Option value="ar-SA">🇸🇦 中东 — Family Drama / Business Empire</Option>
            <Option value="tr-TR">🇹🇷 土耳其 — Mafia Romance / Revenge</Option>
            <Option value="ja-JP">🇯🇵 日本 — Slice of Life / Office Romance</Option>
            <Option value="ko-KR">🇰🇷 韩国 — Chaebol Romance / Fantasy</Option>
            <Option value="es-MX">🇲🇽 拉美 — Telenovela / Family Legacy</Option>
            <Option value="th-TH">🇹🇭 东南亚 — Lakorn Romance / Comedy</Option>
          </Select>
        </Form.Item>

        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="情节模板" tooltip="AI 自动匹配最佳短剧结构模板（含集级节奏、钩子位置、付费点）">
              {matchedTemplate ? (
                <Tag color="blue" style={{ fontSize: 13, padding: '4px 8px' }}>
                  {matchedTemplate.genre_cn} ({matchedTemplate.total_episodes}集)
                </Tag>
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>生成时自动匹配</Text>
              )}
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label=" ">
              <Button
                type={multiVersion ? 'primary' : 'dashed'}
                size="small"
                icon={<ExperimentOutlined />}
                onClick={() => setMultiVersion(!multiVersion)}
                style={{ marginTop: 4 }}
              >
                {multiVersion ? '✓ 多版本对比' : '多版本对比'}
              </Button>
            </Form.Item>
          </Col>
        </Row>
          </>
        )}

        <div style={{ textAlign: 'center', marginTop: 32 }}>
          {inputTab === 'script' ? (
            <Space direction="vertical" size="middle">
              <Text type="secondary">方式一：点击下方按钮将已粘贴的剧本内容分集</Text>
              <Button
                type="primary"
                size="large"
                icon={<FileTextOutlined />}
                onClick={handleUploadAndSplit}
                loading={generationStatus === 'generating'}
                disabled={!formContent.trim()}
                style={{ minWidth: 200, height: 48, fontSize: 16 }}
              >
                {generationStatus === 'generating' ? '处理中...' : '上传并分集'}
              </Button>
              <Text type="secondary">方式二：直接拖拽文件到上方上传区，自动上传并分集</Text>
            </Space>
          ) : (
            <Button
              type="primary"
              size="large"
              icon={generationStatus === 'generating' ? <LoadingOutlined /> : <PlayCircleOutlined />}
              onClick={handleGenerate}
              loading={generationStatus === 'generating'}
              style={{ minWidth: 200, height: 48, fontSize: 16 }}
            >
              {generationStatus === 'generating' ? '生成中...' : '开始生成剧本'}
            </Button>
          )}
        </div>
      </Form>

      {/* 生成进度 */}
      {generationStatus === 'generating' && (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Progress
            percent={generationProgress}
            status="active"
            strokeColor={{ from: '#0066cc', to: '#34c759' }}
          />
          <Text type="secondary">
            <LoadingOutlined style={{ marginRight: 8 }} />
            AI 正在分析内容并生成剧本，请稍候...
          </Text>
        </div>
      )}

      {/* 生成失败 */}
      {generationStatus === 'failed' && (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <div style={{ color: '#ff3b30', marginBottom: 16 }}>
            <CloseCircleOutlined style={{ fontSize: 48 }} />
            <Title level={4} type="danger">生成失败</Title>
            <Text type="danger">{generationError}</Text>
          </div>
          <Button type="primary" onClick={handleGenerate}>
            重新生成
          </Button>
        </div>
      )}
    </div>
  );

  // ============ 渲染：上传标签页 ============
  const renderUploadTabs = () => (
    <div style={{ padding: '24px', height: 'calc(100vh - 120px)', overflow: 'auto' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Title level={2}>
            <FileTextOutlined style={{ marginRight: 12 }} />
            故事剧本创作
          </Title>
          <Text type="secondary" style={{ fontSize: 16 }}>
            选择一种方式开始创作您的短剧剧本
          </Text>
        </div>

        <Tabs
          activeKey={inputTab}
          onChange={(key) => {
            setInputTab(key);
            setGenerationStatus('idle');
            setGenerationProgress(0);
            setGenerationError(null);
          }}
          type="card"
          size="large"
          centered
          style={{ marginBottom: 24 }}
          items={[
            { key: 'novel', label: <span><BookOutlined /> 上传小说</span> },
            { key: 'script', label: <span><FileTextOutlined /> 上传剧本</span> },
            { key: 'idea', label: <span><BulbOutlined /> 上传想法</span> },
          ]}
        />

        {renderUploadForm()}
      </div>
    </div>
  );

  // ============ 渲染：场景列表 ============
  const renderScenes = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>场景列表</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddScene}>
          添加场景
        </Button>
      </div>

      <List
        dataSource={currentScenes}
        renderItem={(scene) => (
          <Card
            key={scene.id}
            style={{ marginBottom: 16 }}
            actions={[
              <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditScene(scene)}>
                编辑
              </Button>,
              <Button key="preview" type="link" icon={<EyeOutlined />}>
                预览
              </Button>,
              <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteScene(scene.id)}>
                删除
              </Button>,
            ]}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <Title level={5} style={{ marginBottom: 8 }}>{scene.title}</Title>
                <Text type="secondary">{scene.description}</Text>

                <div style={{ marginTop: 12 }}>
                  <Space size={[8, 8]} wrap>
                    <Tag icon={<EnvironmentOutlined />} color="blue">{scene.location}</Tag>
                    <Tag icon={<ClockCircleOutlined />} color="green">{scene.timeOfDay}</Tag>
                    <Tag icon={<UserOutlined />} color="purple">角色：{scene.characters.length}</Tag>
                    <Tag>第 {scene.order} 场</Tag>
                  </Space>
                </div>

                <Divider style={{ margin: '12px 0' }} />

                <div style={{ background: '#ffffff', padding: 12, borderRadius: 4 }}>
                  <Text strong>场景内容：</Text>
                  <div style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{scene.content}</div>
                </div>
              </div>
            </div>
          </Card>
        )}
      />
      {currentScenes.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#aeaeb2' }}>
          <FileTextOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无场景，点击"添加场景"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  // ============ 渲染：角色列表 ============
  const renderCharacters = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>角色管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddCharacter}>
          添加角色
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {currentCharacters.map((character) => (
          <Col xs={24} sm={12} lg={8} key={character.id}>
            <Card
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditCharacter(character)}>
                  编辑
                </Button>,
                <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteCharacter(character.id)}>
                  删除
                </Button>,
              ]}
            >
              <Card.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: character.role === '主角' ? '#0066cc' :
                                      character.role === '配角' ? '#34c759' : '#ff9500',
                      fontSize: 20,
                    }}
                  >
                    {character.name.charAt(0)}
                  </Avatar>
                }
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text strong>{character.name}</Text>
                    <Tag color={character.gender === '男' ? 'blue' : 'pink'}>
                      {character.gender}
                    </Tag>
                  </div>
                }
                description={
                  <div>
                    <div><Text strong>年龄：</Text>{character.age}岁</div>
                    <div><Text strong>角色：</Text>{character.role}</div>
                    <div style={{ marginTop: 8 }}>{character.description}</div>
                  </div>
                }
              />
            </Card>
          </Col>
        ))}
      </Row>
      {currentCharacters.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#aeaeb2' }}>
          <UserOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无角色，点击"添加角色"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  // ============ 渲染：大纲 ============
  const renderOutline = () => (
    <div>
      <Title level={4}>剧本大纲</Title>
      <TextArea
        value={currentEpisode?.description}
        onChange={(e) => {
          if (currentEpisode) {
            const updatedEpisodes = episodes.map(ep =>
              ep.id === currentEpisode.id ? { ...ep, description: e.target.value } : ep
            );
            setEpisodes(updatedEpisodes);
          }
        }}
        placeholder="在这里编写剧本大纲..."
        rows={12}
        style={{ marginBottom: 16 }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Text type="secondary">
          场景数量：{currentScenes.length} | 角色数量：{currentCharacters.length} | 总字数：{currentScenes.reduce((total, scene) => total + scene.content.length, 0)} 字
        </Text>
        <Button type="primary" icon={<SaveOutlined />} onClick={() => message.success('大纲已保存')}>
          保存大纲
        </Button>
      </div>
    </div>
  );

  // ============ 渲染：集数列表 ============
  const renderEpisodeList = () => (
    <div style={{ borderRight: '1px solid #f5f5f7', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #f5f5f7' }}>
        <Title level={4} style={{ margin: 0 }}>
          <FolderOpenOutlined style={{ marginRight: 8 }} />
          集数列表
        </Title>
        <Text type="secondary" style={{ fontSize: 12 }}>共 {uniqueEpisodes.length} 集</Text>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {uniqueEpisodes.map((episode) => (
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
                  第{episode.number}集 {episode.title?.replace(/^第[一二三四五六七八九十百千\d]+集\s*/, '')}
                </Text>
              </div>
              <Space size="small">
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {episode.scenes.length}场景
                </Text>
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

  // ============ 主体提取 ============

  const handleExtractEntities = async () => {
    try {
      const fullText = uniqueEpisodes.map((ep) => ep.description).join('\n');
      if (!fullText.trim()) {
        message.warning('剧本内容为空，无法提取');
        return;
      }
      message.loading({ content: '正在提取角色、场景、道具...', key: 'extract', duration: 0 });

      console.log('[extractEntities] scriptId=', scriptId, 'contentLen=', fullText.length, 'contentStart=', fullText.substring(0, 200));
      // Submit extraction task (async)
      const { task_id } = await scriptService.extractEntitiesAsync(fullText, scriptId!);

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await scriptService.getExtractionStatus(task_id);
          if (status.status === 'completed') {
            clearInterval(pollInterval);
            message.destroy('extract');
            const data = status.result;
            (() => {
              const sc = (data.locations || []).map((l: any, i: number) => ({ id: i + 1, name: typeof l === 'string' ? l : (l.name || ''), description: typeof l === 'object' ? (l.description || '') : '', type: '室内', environment: '', size: '中等', tags: [] }));
              const ch = (data.characters || []).map((c: any, i: number) => {
                const ageMap: Record<string, number> = { '少年': 16, '青年': 25, '中年': 42, '老年': 65 };
                return {
                  id: i + 1,
                  name: c.name || '',
                  description: c.description || c.personality || '',
                  age: ageMap[c.age_range] || (c.age_range ? 25 : 25),
                  gender: c.gender || (c.role === '反派' ? '男' : ''),
                  occupation: c.occupation || '',
                  personality: c.personality || c.description || '',
                  appearance: c.appearance || '',
                  tags: [c.role || '配角'],
                };
              });
              const pr = (data.props || []).map((p: any, i: number) => ({ id: i + 1, name: typeof p === 'string' ? p : (p.name || ''), description: typeof p === 'object' ? (p.description || '') : '', category: '其他', material: '', size: '小型', tags: [] }));
              const wid = getWorkId();
              if (wid) {
                Promise.all([
                  persistState('scenes', sc, wid),
                  persistState('characters', ch, wid),
                  persistState('props', pr, wid),
                ]).catch(() => {});
                // Also persist to backend database so assets survive across machines
                Promise.allSettled([
                  ...ch.map((c: any) => assetService.createCharacter({
                    name: c.name,
                    description: c.description,
                    age: c.age || 25,
                    gender: c.gender || '其他',
                    role: (c.tags && c.tags[0]) || '配角',
                  }).catch(() => {})),
                  ...sc.map((s: any) => assetService.createScene({
                    title: s.name,
                    description: s.description,
                    location: s.type || '',
                    timeOfDay: s.environment || '',
                    content: s.description || '',
                  }).catch(() => {})),
                ]).catch(() => {});
              }
              sessionStorage.setItem('current_script', JSON.stringify({ episodes: JSON.parse(JSON.stringify(episodes)), generatedScriptTitle, title: generatedScriptTitle }));
              message.success('提取完成：' + ch.length + ' 角色、' + sc.length + ' 场景、' + pr.length + ' 道具');
              const w = getWorkId(); navigate(w ? '/scene?workId=' + w : '/scene');
            })();
          } else if (status.status === 'failed') {
            clearInterval(pollInterval);
            message.destroy('extract');
            message.error(status.error || '提取失败');
          }
        } catch { clearInterval(pollInterval); message.destroy('extract'); }
      }, 2000);
    } catch (e: any) {
      message.destroy('extract');
      message.error(e?.message || '提取请求失败');
    }
  };

  // ============ 全局设置状态 ============
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [scriptSettings, setScriptSettings] = useState({
    videoRatio: '16:9',
    creationMode: 'ai',
    styleReference: [] as string[],
    videoQuality: '1080p',
    frameRate: 30,
    aiCharacterCount: 2,
    scriptLength: 5,
    styleCategory: '',
    styleDescription: '',
  });

  const updateSetting = (key: string, value: any) => {
    setScriptSettings((prev) => ({ ...prev, [key]: value }));
  };

  const videoRatioOptions = [
    { value: '16:9', label: '16:9 (横)' },
    { value: '9:16', label: '9:16 (竖)' },
    { value: '1:1', label: '1:1 (方)' },
    { value: '4:3', label: '4:3' },
  ];

  // ============ 渲染：分集剧本展示 ============
  const renderScriptEditor = () => (
    <div style={{ height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部主体提取栏 */}
      <div style={{
        padding: '8px 24px', background: '#fff', borderBottom: '1px solid #e5e5ea',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button size="small" icon={<ArrowLeftOutlined />} onClick={handleBackToUpload}>返回</Button>
          <Title level={5} style={{ margin: 0 }}>
            <FileTextOutlined style={{ marginRight: 6 }} />
            {generatedScriptTitle || currentEpisode?.title || '剧本'}
          </Title>
          <Tag color="success" style={{ fontSize: 12 }}>已生成</Tag>
        </div>
        <Space>
          <Button
            icon={<SaveOutlined />}
            onClick={handleSaveScript}
            loading={savingScript}
          >
            {savingScript ? '保存中...' : '保存剧本'}
          </Button>
          <Dropdown
            menu={{
              items: [
                { key: 'xiaoyunque', label: '小云雀 (纯文本)', icon: <DownloadOutlined /> },
                { key: 'libtv', label: 'LibTV (分镜JSON)', icon: <DownloadOutlined /> },
                { key: 'jurilu', label: '巨日禄 (纯文本)', icon: <DownloadOutlined /> },
                { type: 'divider' },
                { key: 'all', label: '一键导出全部', icon: <DownloadOutlined /> },
              ],
              onClick: async ({ key }) => {
                if (!scriptId) { message.warning('请先生成剧本'); return; }
                if (uniqueEpisodes.length === 0) { message.warning('剧本内容加载中，请稍后再试'); return; }
                const hide = message.loading(`正在导出到 ${key === 'all' ? '全部平台' : key}...`, 0);
                try {
                  const result = await scriptService.exportToPlatform(
                    scriptId, key as any, key === 'libtv' ? 'storyboard_json' : 'raw_text'
                  );
                  hide();
                  if (key === 'all') {
                    const exports = (result as any)?.exports || {};
                    const passed = Object.values(exports).filter((e: any) => e?.validation_passed).length;
                    message.success(`已导出 ${passed}/${Object.keys(exports).length} 个平台`);
                    const content = JSON.stringify(exports, null, 2);
                    const blob = new Blob([content], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a'); a.href = url;
                    a.download = `script_${scriptId}_exports.json`; a.click();
                    URL.revokeObjectURL(url);
                  } else {
                    const data = (result as any)?.data || result;
                    const exp = data?.export;
                    const exportedContent = exp?.content || data?.content || '';
                    message.success(`导出成功 (${exp?.target || key}, ${exp?.format || 'raw_text'})`);
                    const blob = new Blob([exportedContent], {
                      type: 'text/plain',
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a'); a.href = url;
                    a.download = `script_${scriptId}_${key}.txt`;
                    a.click(); URL.revokeObjectURL(url);
                  }
                } catch (e: any) {
                  hide(); message.error(`导出失败: ${e?.message || e}`);
                }
              },
            }}
          >
            <Button icon={<DownloadOutlined />}>导出</Button>
          </Dropdown>
          <Button
            type="primary"
            size="middle"
            icon={<ExperimentOutlined />}
            onClick={handleExtractEntities}
          >
            主体提取
          </Button>
        </Space>
      </div>

      {/* 下方内容区 */}
      <div style={{ flex: 1, display: 'flex', gap: 16, padding: '16px 24px', overflow: 'hidden' }}>
        {/* 左侧集数列表 */}
        <div style={{ width: 220, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '16px', borderBottom: '1px solid #f5f5f7' }}>
            <Title level={5} style={{ margin: 0 }}>
              <FolderOpenOutlined style={{ marginRight: 6 }} />
              集数列表
            </Title>
            <Text type="secondary" style={{ fontSize: 12 }}>共 {uniqueEpisodes.length} 集</Text>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {uniqueEpisodes.map((episode) => (
              <div
                key={episode.id}
                onClick={() => setActiveEpisodeId(episode.id)}
                style={{
                  padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #f5f5f7',
                  backgroundColor: activeEpisodeId === episode.id ? '#e8f2fd' : 'transparent',
                }}
              >
                <Text strong style={{ fontSize: 13, color: activeEpisodeId === episode.id ? '#0066cc' : undefined }}>
                  第{episode.number}集 {episode.title?.replace(/^第[一二三四五六七八九十百千\d]+集\s*/, '')}
                </Text>
              </div>
            ))}
          </div>
        </div>

        {/* 中间剧本内容 */}
        <div style={{ flex: 1, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
            {currentEpisode ? (
              <TextArea
                value={currentEpisode.description || ''}
                onChange={(e) => handleEpisodeContentChange(e.target.value)}
                placeholder="在此编辑剧本内容…"
                style={{
                  fontFamily: '"Noto Serif SC", STSong, serif',
                  fontSize: 14,
                  lineHeight: 2,
                  color: '#1d1d1f',
                  minHeight: 300,
                  height: '100%',
                  border: '1px solid #e5e7eb',
                  borderRadius: 6,
                  padding: '24px 28px',
                  resize: 'vertical',
                  background: '#fafafa',
                }}
              />
            ) : (
              <div style={{
                background: '#fafafa', borderRadius: 6, padding: '24px 28px',
                fontFamily: '"Noto Serif SC", STSong, serif', fontSize: 14, lineHeight: 2,
                color: '#9ca3af', minHeight: 300, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                选择左侧集数查看剧本内容
              </div>
            )}
          </div>
        </div>

      </div>

      {/* 多版本对比弹窗 */}
      <Modal
        title={<span><TrophyOutlined style={{ marginRight: 8, color: '#faad14' }} />多版本对比 — 选择最佳剧本</span>}
        open={versionModalOpen}
        onCancel={() => setVersionModalOpen(false)}
        onOk={() => {
          // 记录用户版本选择
          if (userId && selectedVersion && multiVersions.length > 0) {
            scriptService.recordVersionChoice({
              user_id: String(userId),
              chosen_version: selectedVersion,
              versions: multiVersions.map((v: any) => ({
                version: v.version, label: v.label, score: v.score,
              })),
              style: formStyle,
              theme: formTheme,
              length: formLength,
              auto_choice: selectedVersion === multiWinner?.version,
            }).then((res: any) => {
              if (res?.data?.total_scripts >= 3) {
                message.info(`已为您生成 ${res.data.total_scripts} 个剧本，偏好学习已启动`)
              }
            }).catch(() => {})
          }
          setVersionModalOpen(false)
        }}
        okText="确认选择"
        width={960}
      >
        {multiComparison && (
          <Alert
            type="info"
            message={`推荐「${multiWinner?.version}」(${multiWinner?.score}分) — ${multiComparison?.verdict_summary || ''}`}
            style={{ marginBottom: 12 }}
            showIcon
          />
        )}
        <Row gutter={12}>
          {multiVersions.map((v: any) => {
            const isWinner = v.version === multiWinner?.version
            const colors: Record<string, string> = { A: '#1890ff', B: '#eb2f96', C: '#722ed1' }
            return (
              <Col span={8} key={v.version}>
                <Card size="small" hoverable
                  style={{ borderColor: isWinner ? '#faad14' : undefined, borderWidth: isWinner ? 2 : 1 }}
                  title={<Space><Tag color={colors[v.version]}>{v.version} — {v.label}</Tag>{isWinner && <Tag color="gold"><StarOutlined /> 最佳</Tag>}</Space>}
                  extra={<Text strong>{v.score}分</Text>}
                >
                  <Text type="success" style={{ fontSize: 11 }}>{(v.strengths || []).slice(0, 2).join('、') || '—'}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>{v.script_content?.length || 0} 字 · {v.episodes?.length || 0} 集</Text>
                  <Button
                    type={selectedVersion === v.version ? 'primary' : 'default'}
                    size="small" block
                    onClick={() => {
                      setSelectedVersion(v.version)
                      if (v.episodes?.length > 0) {
                        const parsedEpisodes = v.episodes.map((ep: any) => ({
                          id: `ep-${ep.episode_number || 1}-${Date.now().toString(36)}`,
                          title: ep.title || `第${ep.episode_number || 1}集`,
                          number: ep.episode_number || 1,
                          scenes: [], characters: [],
                          description: ep.content || '',
                        }))
                        setEpisodes(parsedEpisodes)
                        if (parsedEpisodes.length > 0) setActiveEpisodeId(parsedEpisodes[0].id)
                      }
                    }}
                    style={{ marginTop: 8 }}
                  >
                    {selectedVersion === v.version ? '✓ 已选择' : '选择此版本'}
                  </Button>
                </Card>
              </Col>
            )
          })}
        </Row>
      </Modal>

      {/* ── 对话式意图挖掘 Modal ── */}
      <Modal
        title={<span><BulbOutlined style={{ marginRight: 8, color: '#faad14' }} />完善您的想法</span>}
        open={intentModalOpen}
        onCancel={() => {
          setIntentModalOpen(false);
          setGenerationStatus('idle');
          setGenerationProgress(0);
        }}
        footer={[
          <Button key="skip" onClick={() => {
            // Skip intent mining, use raw outline
            setIntentModalOpen(false);
            setGenerationStatus('generating');
            setGenerationProgress(30);
            const doGenerate = async () => {
              const result = await scriptService.generateScriptFromOutlineSync({
                title: formTitle, outline: formContent,
                theme: formTheme, length: formLength,
                style: formStyle, setting: formSetting,
                user_id: String(userId || 'anonymous'),
                target_locale: targetLocale,
              });
              setGenerationProgress(100);
              setGeneratedScriptTitle(result.title);
              const eps: Episode[] = result.episodes.map((ep: any) => ({
                id: `ep-${ep.episode_number || 1}-${Date.now().toString(36)}`,
                title: ep.title || `第${ep.episode_number || 1}集`,
                number: ep.episode_number || 1,
                scenes: [], characters: [],
                description: ep.content || '',
              }));
              setEpisodes(eps);
              setGenerationStatus('completed');
              if (eps.length > 0) setActiveEpisodeId(eps[0].id);
              latestEpisodesRef.current = eps;
              latestResultRef.current = result;
            };
            doGenerate().catch((err) => {
              setGenerationStatus('failed');
              setGenerationError(err?.message || '生成失败');
            });
          }}>
            跳过，直接生成
          </Button>,
          <Button
            key="confirm" type="primary"
            loading={intentMining}
            disabled={Object.keys(intentAnswers).length < intentQuestions.length}
            onClick={() => {
              setIntentMining(true);
              handleIntentConfirm().finally(() => setIntentMining(false));
            }}
          >
            确认偏好，开始生成
          </Button>,
        ]}
        width={640}
      >
        {intentDetected && (
          <Alert
            type="success"
            message={`检测到「${intentDetected.genre}」题材，建议风格「${intentDetected.style}」`}
            style={{ marginBottom: 16 }}
            showIcon
          />
        )}
        {intentQuestions.map((q) => (
          <div key={q.id} style={{ marginBottom: 20 }}>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>{q.question}</Text>
            <Space wrap>
              {q.options.map((opt) => (
                <Button
                  key={opt}
                  type={intentAnswers[q.id] === opt ? 'primary' : 'default'}
                  size="small"
                  onClick={() => setIntentAnswers(prev => ({ ...prev, [q.id]: opt }))}
                >
                  {opt}
                </Button>
              ))}
            </Space>
          </div>
        ))}
      </Modal>

    </div>
  );

  // ============ 主渲染 ============
  // 生成完成或已有分集数据时显示分集编辑器，否则显示上传视图
  // Persist state for cross-navigation (sidebar switches)
  useEffect(() => {
    if (episodes.length > 0 && generationStatus === 'completed') {
      persistState('script', {
        generationStatus: 'completed', generationProgress: 100,
        generatedScriptTitle: generatedScriptTitle || formTitle,
        episodes: episodes, scriptId: scriptId,
      });
    }
  }, [episodes, generationStatus]);

  const showEditor = generationStatus === 'completed' || (generationStatus === 'idle' && episodes.length > 0);

  return showEditor ? renderScriptEditor() : renderUploadTabs();
};

export default Script;
