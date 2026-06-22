import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
} from 'antd';
import { usePipelinePersistence, clearPipelineStorage } from '@/hooks/usePipelinePersistence';
import { pipelineService } from '@/services/pipelineService';
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
} from '@ant-design/icons';
import { scriptService } from '@/services/scriptService';
import { workService } from '@/services/workService';

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
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 表单值
  const [formTitle, setFormTitle] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formTheme, setFormTheme] = useState('成长');
  const [formStyle, setFormStyle] = useState('浪漫喜剧');
  const [formLength, setFormLength] = useState('短篇');
  const [formSetting, setFormSetting] = useState('现代都市');

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
  const { saveState: persistState, loadState: loadPersisted, restoreFromBackend, getWorkId, setWorkId, userId, saveAllToBackend } = usePipelinePersistence();
  const STORAGE_KEY = `script_page_state_${userId}`;

  const saveState = (state: Partial<{
    episodes: Episode[]
    generatedScriptTitle: string
    generationStatus: GenerationStatus
    generationProgress: number
    taskId: string
    scriptId: number
  }>) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {}
  };

  const loadState = () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  };

  const clearState = () => {
    localStorage.removeItem(STORAGE_KEY);
  };

  // ============ 初始化：恢复上次的状态 ============
  useEffect(() => {
    const initLoad = async () => {
      const urlWorkId = searchParams.get('workId');

      if (urlWorkId) {
        // URL 明确指定了 workId → restoreFromBackend 会自动清旧数据并从后端恢复
        clearState();
        await restoreFromBackend(urlWorkId);
      } else {
        // 无 workId → 全新开始，清除之前所有 pipeline 状态
        clearPipelineStorage(userId);
        clearState();
      }

      // 从 localStorage 恢复（多源尝试，确保不丢数据）
      let saved = loadPersisted('script');
      if (!saved) {
        saved = loadState();  // script_page_state_{userId}
      }
      if (!saved && urlWorkId) {
        // 最后尝试：从后端重新加载
        try {
          const resp = await pipelineService.getPipelineState(urlWorkId);
          const data = (resp as any)?.data;
          if (data?.script) saved = data.script;
        } catch {}
      }

      if (saved) {
        if (saved.generationStatus === 'completed' && saved.episodes?.length > 0) {
          setEpisodes(saved.episodes || []);
          setGeneratedScriptTitle(saved.generatedScriptTitle || '');
          setGenerationStatus('completed');
          setGenerationProgress(100);
          if (saved.scriptId) {
            setScriptId(saved.scriptId);
          }
          if (saved.episodes?.length > 0) {
            setActiveEpisodeId(saved.episodes[0].id);
          }
        } else if (saved.generationStatus === 'generating' && saved.taskId) {
          scriptService.getGenerationStatus(saved.taskId).then((status) => {
            if (status && status.status !== 'failed') {
              setGenerationStatus('generating');
              setGenerationProgress(saved.generationProgress || 0);
              setGeneratedScriptTitle(saved.generatedScriptTitle || '');
              pollGenerationStatus(saved.taskId);
            } else {
              clearState();
            }
          }).catch(() => {
            clearState();
          });
        } else {
          clearState();
        }
      }
    };
    initLoad();
  }, [searchParams]);

  // ============ 轮询逻辑 ============
  const pollGenerationStatus = useCallback((id: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const status = await scriptService.getGenerationStatus(id);
        if (status) {
          setGenerationProgress(status.progress || 0);
          saveState({
            generationStatus: 'generating',
            generationProgress: status.progress || 0,
            taskId: id,
            generatedScriptTitle: formTitle,
          });

          if (status.status === 'completed') {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setGenerationStatus('completed');
            setGenerationProgress(100);
            message.success('剧本生成完成！');

            if (status.result) {
              const script = status.result;
              setGeneratedScriptTitle(script.title || formTitle);
              // 优先使用后端预拆分的分集数据
              if (script.episodes && script.uniqueEpisodes.length > 0) {
                const backendEpisodes: Episode[] = script.episodes.map((ep: any) => ({
                  id: `ep-${ep.episode_number || ep.episodeNumber || 1}-${Date.now().toString(36)}`,
                  title: ep.title || `第${ep.episode_number || 1}集`,
                  number: ep.episode_number || ep.episodeNumber || 1,
                  scenes: [],
                  characters: [],
                  description: ep.content || '',
                }));
                setEpisodes(backendEpisodes);
                if (backendEpisodes.length > 0) setActiveEpisodeId(backendEpisodes[0].id);
              } else {
                parseScriptToEpisodes(script.content || '', script.title || formTitle);
              }
            } else {
              setGeneratedScriptTitle(formTitle);
              createDefaultEpisodes(formTitle);
            }
          } else if (status.status === 'failed') {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setGenerationStatus('failed');
            setGenerationError(status.error || status.error_message || '剧本生成失败，请重试');
            message.error(status.error || status.error_message || '剧本生成失败，请重试');
            saveState({ generationStatus: 'failed' });
          }
        }
      } catch (err: any) {
        // 404 = 任务已不存在，停止轮询
        if (err?.response?.status === 404) {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          clearState();
          setGenerationStatus('idle');
          console.log('任务已过期，已停止轮询');
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
    if (uniqueEpisodes.length > 0) {
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
        });
      } else if (inputTab === 'script') {
        response = await scriptService.generateScript({
          title: formTitle,
          description: formContent.slice(0, 500),
          genre: 'drama' as any,
          target_duration_minutes: formLength === '短篇' ? 10 : formLength === '中篇' ? 30 : 60,
          character_count: 3,
          style: formStyle as any,
          theme: formTheme,
        });
      } else if (inputTab === 'idea') {
        // 同步生成，直接等 AI 返回结果（不走轮询）
        setGenerationProgress(30);
        const result = await scriptService.generateScriptFromOutlineSync({
          title: formTitle, outline: formContent,
          theme: formTheme, length: formLength,
          style: formStyle, setting: formSetting,
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
        setGenerationProgress(100);
        if (parsedEpisodes.length > 0) setActiveEpisodeId(parsedEpisodes[0].id);

        // 保存到 localStorage 和后端
        const scriptData = {
          episodes: JSON.parse(JSON.stringify(parsedEpisodes)),
          generatedScriptTitle: result.title,
          generationStatus: 'completed', generationProgress: 100,
        };
        // 先确保有作品
        let wId = getWorkId();
        if (!wId) {
          try {
            const work = await workService.createWork({
              title: result.title, type: '短剧', description: '', userId: userId,
            });
            if (work?.id) { setWorkId(work.id); wId = work.id; }
          } catch (e) { console.error('Create work failed:', e); }
        }
        // 确保 wId 存在
        if (!wId) {
          try {
            const work = await workService.createWork({
              title: result.title, type: '短剧', description: '', userId: userId,
            });
            if (work?.id) { setWorkId(work.id); wId = work.id; }
          } catch (e) { console.error('Create work failed:', e); }
        }

        // 使用 saveAllToBackend（带序列化锁，不会丢失其他 key）
        if (wId) {
          await saveAllToBackend(wId, { script: scriptData });
        }

        message.success(`剧本生成完成，共 ${result.total_episodes} 集`);
        return;
      }

      if (response?.task_id) {
        const id = response.task_id;
        setGenerationProgress(10);
        saveState({ generationStatus: 'generating', generationProgress: 10, taskId: id, generatedScriptTitle: formTitle });
        message.info('剧本生成任务已提交，正在生成中...');
        pollGenerationStatus(id);
      } else {
        throw new Error('未获取到任务ID');
      }
    } catch (err: any) {
      setGenerationStatus('failed');
      setGenerationError(err?.response?.data?.detail || err?.message || '生成请求失败');
      message.error('生成请求失败，请重试');
    }
  };

  // ============ 上传并分集（上传完整剧本，后端按集拆分） ============
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
      const parsedEpisodes: Episode[] = result.episodes.map((ep) => ({
        id: `ep-${ep.episode_number}-${Date.now().toString(36)}`,
        title: ep.title,
        number: ep.episode_number,
        scenes: [],
        characters: [],
        description: ep.content,
      }));

      setScriptId(result.script_id);
      setEpisodes(parsedEpisodes);
      setGeneratedScriptTitle(result.title);
      setGenerationStatus('completed');
      setGenerationProgress(100);

      // 立即持久化到 localStorage
      saveState({
        episodes: JSON.parse(JSON.stringify(parsedEpisodes)),
        generatedScriptTitle: result.title,
        generationStatus: 'completed',
        generationProgress: 100,
        scriptId: result.script_id,
      });

      // 立即创建作品并保存到后端（不依赖 debounce）
      const scriptData = {
        episodes: JSON.parse(JSON.stringify(parsedEpisodes)),
        generatedScriptTitle: result.title,
        generationStatus: 'completed',
        generationProgress: 100,
        scriptId: result.script_id,
      };
      persistState('script', scriptData);  // 先写 localStorage
      let wId = getWorkId();
      if (!wId) {
        try {
          const work = await workService.createWork({
            title: result.title,
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
      if (wId) {
        // 立即保存到后端（读取现有数据 → 合并 → 写入，避免覆盖其他 key）
        try {
          const existingResp = await pipelineService.getPipelineState(wId);
          const existing = (existingResp as any)?.data || {};
          existing.script = JSON.parse(
            localStorage.getItem(`pipeline_${userId}_script`) || 'null'
          );
          existing.updatedAt = new Date().toISOString();
          await pipelineService.savePipelineState(wId, existing);
        } catch {
          // 回退：至少保存 script
          const raw = localStorage.getItem(`pipeline_${userId}_script`);
          pipelineService.savePipelineState(wId, {
            script: raw ? JSON.parse(raw) : null,
            updatedAt: new Date().toISOString(),
          }).catch(() => {});
        }
      }

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
      saveState(scriptData);

      // 仅保存到已有 workId，不创建新作品（创建由 handleUploadAndSplit/handleGenerate 负责）
      (async () => {
      const workId = getWorkId();
      if (workId) {
        try {
          localStorage.setItem(`pipeline_${userId}_script`, JSON.stringify(scriptData));
          const resp = await pipelineService.getPipelineState(workId);
          const existing = (resp as any)?.data || {};
          existing.script = scriptData;
          if (!existing.updatedAt) existing.updatedAt = (new Date()).toISOString();
          await pipelineService.savePipelineState(workId, existing);
        } catch {}
      }
      })();
    }
  }, [episodes, generationStatus, generatedScriptTitle, generationProgress]);

  // 返回上传视图
  const handleBackToUpload = () => {
    clearState();
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
  const handleFileUpload = (file: File): boolean => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      setFormContent(text);
      message.success(`已加载文件: ${file.name}`);
    };
    reader.onerror = () => {
      message.error('文件读取失败');
    };
    reader.readAsText(file);
    return false; // 阻止自动上传
  };

  // ============ 渲染：上传视图 ============
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
                ? '在此粘贴您的剧本内容...'
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
              accept={inputTab === 'novel' ? '.txt,.md,.docx' : '.txt,.md,.doc,.docx'}
              multiple={false}
              beforeUpload={handleFileUpload}
              maxCount={1}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                {inputTab === 'novel' ? '支持 .txt, .md 文件' : '支持 .txt, .md, .doc 文件'}
              </p>
            </Dragger>
          </Form.Item>
        )}

        {inputTab !== 'script' && (
          <>
            <Row gutter={24}>
          <Col span={8}>
            <Form.Item label="剧本主题">
              <Input
                placeholder="例如：爱情、复仇、成长"
                value={formTheme}
                onChange={(e) => setFormTheme(e.target.value)}
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="剧本风格">
              <Select value={formStyle} onChange={setFormStyle}>
                <Option value="浪漫喜剧">浪漫喜剧</Option>
                <Option value="悬疑推理">悬疑推理</Option>
                <Option value="科幻未来">科幻未来</Option>
                <Option value="古风历史">古风历史</Option>
                <Option value="都市情感">都市情感</Option>
                <Option value="奇幻冒险">奇幻冒险</Option>
                <Option value="恐怖惊悚">恐怖惊悚</Option>
                <Option value="动作武侠">动作武侠</Option>
              </Select>
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item label="剧本长度">
              <Select value={formLength} onChange={setFormLength}>
                <Option value="短篇">短篇（~10分钟）</Option>
                <Option value="中篇">中篇（~30分钟）</Option>
                <Option value="长篇">长篇（~60分钟）</Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>

        <Form.Item label="故事背景">
          <Input
            placeholder="例如：现代都市、古代宫廷、未来世界"
            value={formSetting}
            onChange={(e) => setFormSetting(e.target.value)}
          />
        </Form.Item>
          </>
        )}

        <div style={{ textAlign: 'center', marginTop: 32 }}>
          {inputTab === 'script' ? (
            <Button
              type="primary"
              size="large"
              icon={<FileTextOutlined />}
              onClick={handleUploadAndSplit}
              loading={generationStatus === 'generating'}
              style={{ minWidth: 200, height: 48, fontSize: 16 }}
            >
              {generationStatus === 'generating' ? '处理中...' : '上传并分集'}
            </Button>
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
                  {episode.title}
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

  // ============ 主体提取弹窗 ============
  const [isExtractModalOpen, setIsExtractModalOpen] = useState(false);
  const [extractedEntities, setExtractedEntities] = useState<{
    characters: { name: string; role: string; description: string }[]
    locations: string[]
    items: string[]
  } | null>(null);

  const handleExtractEntities = async () => {
    try {
      const fullText = uniqueEpisodes.map((ep) => ep.description).join('\n');
      if (!fullText.trim()) {
        message.warning('剧本内容为空，无法提取');
        return;
      }
      message.loading({ content: '正在提取角色、场景、道具...', key: 'extract', duration: 0 });
      const data = await scriptService.extractEntities(fullText);
      message.destroy('extract');

      // 构建场景数据（从地点列表）
      const extractedScenes = (data.locations || []).map((loc: any, idx: number) => ({
        id: idx + 1,
        name: typeof loc === 'string' ? loc : (loc.name || ''),
        description: typeof loc === 'object' ? (loc.description || '') : '',
        type: '室内',
        environment: '',
        size: '中等',
        tags: [],
      }));

      // 构建角色数据
      const extractedCharacters = (data.characters || []).map((c: any, idx: number) => ({
        id: idx + 1,
        name: c.name || '',
        description: c.description || '',
        age: 25,
        gender: c.role === '反派' ? '男' : '女',
        occupation: '',
        personality: c.description || '',
        appearance: '',
        tags: [c.role || '配角'],
      }));

      // 构建道具数据
      const extractedProps = (data.props || []).map((p: any, idx: number) => ({
        id: idx + 1,
        name: typeof p === 'string' ? p : (p.name || ''),
        description: typeof p === 'object' ? (p.description || '') : '',
        category: '其他',
        material: '',
        size: '小型',
        tags: [],
      }));

      // 使用 saveAllToBackend（带序列化锁，确保与其他保存不冲突）
      const wId = getWorkId();
      if (wId) {
        await saveAllToBackend(wId, {
          scenes: extractedScenes,
          characters: extractedCharacters,
          props: extractedProps,
        });
      }

      // 存到 sessionStorage（绕过 pipeline 问题，可靠传递剧本数据）
      sessionStorage.setItem('current_script', JSON.stringify({
        episodes: JSON.parse(JSON.stringify(episodes)),
        generatedScriptTitle,
        title: generatedScriptTitle,
      }));

      const totalCount = extractedCharacters.length + extractedScenes.length + extractedProps.length;
      message.success(`提取完成：${extractedCharacters.length} 个角色、${extractedScenes.length} 个场景、${extractedProps.length} 个道具`);
      navigate(`/scene?workId=${wId || ''}`);
    } catch {
      message.destroy('extract');
      message.error('主体提取失败，请重试');
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
        <Button
          type="primary"
          size="middle"
          icon={<ExperimentOutlined />}
          onClick={handleExtractEntities}
        >
          主体提取
        </Button>
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
                  {episode.title}
                </Text>
              </div>
            ))}
          </div>
        </div>

        {/* 中间剧本内容 */}
        <div style={{ flex: 1, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '12px 24px', borderBottom: '1px solid #f5f5f7', display: 'flex', justifyContent: 'flex-end' }}>
            <Button size="small" onClick={() => setSettingsOpen(!settingsOpen)}>
              {settingsOpen ? '收起设置' : '全局设置'}
            </Button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
            <div style={{
              background: '#fafafa', borderRadius: 6, padding: '24px 28px',
              fontFamily: '"Noto Serif SC", STSong, serif', fontSize: 14, lineHeight: 2,
              whiteSpace: 'pre-wrap', color: '#1d1d1f', minHeight: 300,
            }}>
              {currentEpisode?.description || '选择左侧集数查看剧本内容'}
            </div>
          </div>
        </div>

        {/* 右侧全局设置 */}
        {settingsOpen && (
          <div style={{ width: 300, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', overflowY: 'auto' }}>
            <div style={{ padding: '16px', borderBottom: '1px solid #f5f5f7' }}>
              <Title level={5} style={{ margin: 0 }}>
                <SettingOutlined style={{ marginRight: 6 }} />
                全局设置
              </Title>
            </div>
            <div style={{ padding: '12px 16px' }}>
              <Form layout="vertical" size="small">
                <Form.Item label="视频比例">
                  <Select value={scriptSettings.videoRatio} onChange={(v) => updateSetting('videoRatio', v)}>
                    {videoRatioOptions.map((o) => <Option key={o.value} value={o.value}>{o.label}</Option>)}
                  </Select>
                </Form.Item>
                <Form.Item label="画质">
                  <Select value={scriptSettings.videoQuality} onChange={(v) => updateSetting('videoQuality', v)}>
                    <Option value="4k">4K</Option>
                    <Option value="1080p">1080p</Option>
                    <Option value="720p">720p</Option>
                  </Select>
                </Form.Item>
                <Form.Item label="帧率">
                  <Select value={scriptSettings.frameRate} onChange={(v) => updateSetting('frameRate', v)}>
                    <Option value={24}>24 fps</Option>
                    <Option value={30}>30 fps</Option>
                    <Option value={60}>60 fps</Option>
                  </Select>
                </Form.Item>
                <Divider style={{ margin: '8px 0' }} />
                <Form.Item label="创作模式">
                  <Select value={scriptSettings.creationMode} onChange={(v) => updateSetting('creationMode', v)}>
                    <Option value="ai">AI 生成</Option>
                    <Option value="assist">AI 辅助</Option>
                    <Option value="manual">手动</Option>
                  </Select>
                </Form.Item>
                <Form.Item label="角色数量">
                  <InputNumber min={1} max={10} value={scriptSettings.aiCharacterCount} onChange={(v) => updateSetting('aiCharacterCount', v)} style={{ width: '100%' }} />
                </Form.Item>
                <Form.Item label="剧本时长(分钟)">
                  <InputNumber min={1} max={60} value={scriptSettings.scriptLength} onChange={(v) => updateSetting('scriptLength', v)} style={{ width: '100%' }} />
                </Form.Item>
                <Divider style={{ margin: '8px 0' }} />
                <Form.Item label="视频风格">
                  <Select value={scriptSettings.styleCategory} onChange={(v) => updateSetting('styleCategory', v)} placeholder="选择风格" allowClear>
                    <Option value="古风写实">古风写实</Option>
                    <Option value="赛博朋克">赛博朋克</Option>
                    <Option value="都市情感">都市情感</Option>
                    <Option value="日漫">日漫</Option>
                    <Option value="3D国风">3D国风</Option>
                    <Option value="皮克斯风格">皮克斯风格</Option>
                    <Option value="水墨画">水墨画</Option>
                  </Select>
                </Form.Item>
                <Form.Item label="风格描述">
                  <TextArea rows={3} value={scriptSettings.styleDescription}
                    onChange={(e) => updateSetting('styleDescription', e.target.value)}
                    placeholder="描述想要的视频风格..." />
                </Form.Item>
                <Button type="primary" block icon={<SaveOutlined />}
                  onClick={() => message.success('设置已保存')}>
                  保存设置
                </Button>
              </Form>
            </div>
          </div>
        )}
      </div>

      {/* 主体提取弹窗 */}
      <Modal
        title={<><ExperimentOutlined style={{ marginRight: 8 }} />主体提取结果</>}
        open={isExtractModalOpen}
        onCancel={() => setIsExtractModalOpen(false)}
        footer={<Button onClick={() => setIsExtractModalOpen(false)}>关闭</Button>}
        width={640}
      >
        {extractedEntities === null && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <Text type="secondary" style={{ display: 'block', marginTop: 12 }}>AI 正在分析剧本，提取主体信息...</Text>
          </div>
        )}
        {extractedEntities && extractedEntities.characters.length === 0 && extractedEntities.locations.length === 0 && extractedEntities.items.length === 0 && (
          <Text type="secondary">未从剧本中提取到角色和地点信息。</Text>
        )}
        {extractedEntities && (extractedEntities.characters.length > 0 || extractedEntities.locations.length > 0 || extractedEntities.items.length > 0) && (
          <div>
            {extractedEntities.characters.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <Title level={5}>👤 角色 ({extractedEntities.characters.length})</Title>
                <Row gutter={[12, 12]}>
                  {extractedEntities.characters.slice(0, 6).map((c: any, i: number) => (
                    <Col span={12} key={i}>
                      <Card size="small" style={{ background: '#f8f8fa' }}>
                        <Text strong>{c.name}</Text>
                        {c.role && <Tag style={{ marginLeft: 4 }}>{c.role}</Tag>}
                        <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{(c.description || '').slice(0, 60)}</Text>
                      </Card>
                    </Col>
                  ))}
                </Row>
              </div>
            )}
            {extractedEntities.locations.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <Title level={5}>📍 地点 ({extractedEntities.locations.length})</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {extractedEntities.locations.slice(0, 10).map((loc: any, i: number) => (
                    <Tag key={i} color="blue">{typeof loc === 'string' ? loc : loc.name}</Tag>
                  ))}
                </div>
              </div>
            )}
            {extractedEntities.items.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <Title level={5}>📦 关键物品 ({extractedEntities.items.length})</Title>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {extractedEntities.items.slice(0, 12).map((item: any, i: number) => (
                    <Tag key={i} color="orange">{typeof item === 'string' ? item : item.name}</Tag>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );

  // ============ 主渲染 ============
  // 生成完成或已有分集数据时显示分集编辑器，否则显示上传视图
  const showEditor = generationStatus === 'completed' && uniqueEpisodes.length > 0;

  return showEditor ? renderScriptEditor() : renderUploadTabs();
};

export default Script;
