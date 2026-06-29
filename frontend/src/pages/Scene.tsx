import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Card,
  Typography,
  Button,
  Avatar,
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
  Progress,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  TeamOutlined,
  EnvironmentOutlined,
  ToolOutlined,
  CameraOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { scriptService } from '@/services/scriptService';
import { usePipelinePersistence } from '@/hooks/usePipelinePersistence';
import { pipelineService } from '@/services/pipelineService';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

// 场景类型定义
interface SceneItem {
  id: number;
  name: string;
  description: string;
  type: string; // 室内、室外、虚拟等
  environment: string; // 环境描述
  size: string; // 大小
  tags: string[];
  previewUrl?: string;
}

// 角色类型定义
interface CharacterItem {
  id: number;
  name: string;
  description: string;
  age: number;
  gender: string;
  occupation: string;
  personality: string;
  appearance: string;
  tags: string[];
  modelUrl?: string;
}

// 道具类型定义
interface PropItem {
  id: number;
  name: string;
  description: string;
  category: string; // 家具、武器、装饰品等
  material: string;
  size: string;
  tags: string[];
  modelUrl?: string;
}

const Scene: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('scenes');
  const [scenes, setScenes] = useState<SceneItem[]>([]);

  // 从 localStorage / pipeline 加载持久化数据
  useEffect(() => {
    const initLoad = async () => {
      const urlWorkId = searchParams.get('workId');
      if (urlWorkId) {
        // 从后端恢复该项目的数据
        setWorkId(urlWorkId);
        await restoreFromBackend(urlWorkId);
      } else {
        // 无活跃作品，清空显示
        setScenes([]);
        setCharacters([]);
        setProps([]);
        return;
      }

      // 优先从 pipeline localStorage 加载（workId 感知）
      const savedScenes = loadState('scenes');
      const savedCharacters = loadState('characters');
      const savedProps = loadState('props');

      if (savedScenes?.length) setScenes(savedScenes);
      if (savedCharacters?.length) setCharacters(savedCharacters);
      if (savedProps?.length) setProps(savedProps);

      // 回退：从全局 key 加载（兼容旧数据）
      if (!savedScenes?.length && !savedCharacters?.length && !savedProps?.length) {
        const saved = localStorage.getItem('extracted_entities');
        if (saved) {
          try {
            const data = JSON.parse(saved);
            if (data.scenes?.length) setScenes(data.scenes);
            if (data.characters?.length) setCharacters(data.characters);
            if (data.props?.length) setProps(data.props);
          } catch {}
        }
      }

      // 加载预览图像缓存
      const savedImages = localStorage.getItem('scene_preview_images');
      if (savedImages) {
        try { setPreviewImages(JSON.parse(savedImages)); } catch {}
      }
    };
    initLoad();
  }, [searchParams]);

  // 保留的模拟数据引用（已弃用）
  const _mock = []; // deprecated mock data, replaced by extracted_entities
  const [characters, setCharacters] = useState<CharacterItem[]>([]);
  const [props, setProps] = useState<PropItem[]>([]);

  const [editingScene, setEditingScene] = useState<SceneItem | null>(null);
  const [editingCharacter, setEditingCharacter] = useState<CharacterItem | null>(null);
  const [editingProp, setEditingProp] = useState<PropItem | null>(null);
  const [isSceneModalOpen, setIsSceneModalOpen] = useState(false);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState(false);
  const [isPropModalOpen, setIsPropModalOpen] = useState(false);

  // 智能分镜状态
  const { loadState, getWorkId, setWorkId, restoreFromBackend, userId } = usePipelinePersistence();

  // 自动持久化：直接 GET-merge-PUT，不依赖 hook
  useEffect(() => {
    if (scenes.length || characters.length || props.length) {
      localStorage.setItem('extracted_entities', JSON.stringify({
        scenes, characters, props,
        updatedAt: new Date().toISOString(),
      }));
      (async () => {
        const wId = getWorkId();
        if (!wId) return;
        try {
          const resp = await pipelineService.getPipelineState(wId);
          const existing = (resp as any)?.data || {};
          existing.scenes = scenes;
          existing.characters = characters;
          existing.props = props;
          existing.updatedAt = new Date().toISOString();
          await pipelineService.savePipelineState(wId, existing);
          // 也写到 localStorage
          localStorage.setItem(`pipeline_${userId}_scenes`, JSON.stringify(scenes));
          localStorage.setItem(`pipeline_${userId}_characters`, JSON.stringify(characters));
          localStorage.setItem(`pipeline_${userId}_props`, JSON.stringify(props));
        } catch (e) { console.error('Scene save failed:', e); }
      })();
    }
  }, [scenes, characters, props]);
  const navigate = useNavigate();
  const [shotGenerationStatus, setShotGenerationStatus] = useState<'idle' | 'generating' | 'completed' | 'failed'>('idle');
  const [shotGenerationProgress, setShotGenerationProgress] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 智能分镜 — 轮询分镜生成状态
  const pollShotStatus = useCallback((id: string) => {
    pollingRef.current = setInterval(async () => {
      try {
        const status = await scriptService.getShotGenerationStatus(id);
        if (status) {
          setShotGenerationProgress(status.progress || 0);

          if (status.status === 'completed') {
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            setShotGenerationStatus('completed');
            setShotGenerationProgress(100);
            message.success('智能分镜生成完成！');

            // 获取完整结果
            const result = await scriptService.getShotGenerationResult(id);
            if (result.episodes) {
              // 保存到 pipeline localStorage + 后端（不再用旧全局 key）
              const storyboardData = {
                episodes: result.episodes,
                generatedAt: new Date().toISOString(),
              };
              const wId = getWorkId();
              if (wId) {
                // 直接保存 storyboard（不通过 saveAllToBackend，避免 buildFullState 遗漏）
                try {
                  const resp = await pipelineService.getPipelineState(wId);
                  const existing = (resp as any)?.data || {};
                  existing.storyboard = storyboardData;
                  if (!existing.script) {
                    // 从 sessionStorage 恢复 script（防止丢失）
                    const sess = sessionStorage.getItem('current_script');
                    if (sess) { try { existing.script = JSON.parse(sess); } catch {} }
                  }
                  existing.updatedAt = new Date().toISOString();
                  await pipelineService.savePipelineState(wId, existing);
                  // 同步写 localStorage
                  localStorage.setItem(`pipeline_${userId}_storyboard`, JSON.stringify(storyboardData));
                } catch (e) { console.error('Save storyboard failed:', e); }
              }
              navigate(wId ? `/storyboard?workId=${wId}` : '/storyboard');
            }
          } else if (status.status === 'failed') {
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            setShotGenerationStatus('failed');
            message.error(status.error || '智能分镜生成失败');
          }
        }
      } catch (err: any) {
        if (err?.response?.status === 404) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setShotGenerationStatus('idle');
          message.error('分镜任务已过期，请重新生成');
        }
      }
    }, 3000);
  }, [navigate]);

  // 智能分镜 — 开始生成
  const handleSmartShotDivision = useCallback(async () => {
    // 从 sessionStorage 读取（Script 页面主体提取时写入，最可靠）
    let savedState: any = null;
    const sessData = sessionStorage.getItem('current_script');
    if (sessData) { try { savedState = JSON.parse(sessData); } catch {} }
    // 回退到 pipeline/localStorage
    if (!savedState || !savedState.episodes?.length) {
      savedState = loadState('script');
      if (!savedState) {
        const oldData = localStorage.getItem(`script_page_state_${(window as any).__USER_ID__ || 'anonymous'}`);
        if (oldData) { try { savedState = JSON.parse(oldData); } catch {} }
      }
    }
    if (!savedState) savedState = {} as any;
    const episodes = (savedState as any).episodes || [];

    // 拼接所有集的描述作为剧本内容
    const scriptContent = episodes.map((ep: any) =>
      ep.description || ep.content || ''
    ).join('\n\n');

    if (!scriptContent.trim()) {
      message.warning('请先在剧本页面生成或编写剧本内容');
      return;
    }

    const title = (savedState as any).generatedScriptTitle || '未命名剧本';

    setShotGenerationStatus('generating');
    setShotGenerationProgress(0);

    try {
      const response = await scriptService.generateShots({
        title,
        script: scriptContent,
        episodeCount: episodes.length || 1,
        episodeContents: episodes.map((ep: any) => ep.description || ep.content || ''),
        style: '写实风格',
        sceneRefs: scenes.map(s => s.name),
        characterNames: characters.map(c => c.name),
      });

      if (response?.task_id) {
        setShotGenerationProgress(10);
        message.info('智能分镜任务已提交，正在分析剧本...');
        pollShotStatus(response.task_id);
      } else {
        throw new Error('未获取到任务ID');
      }
    } catch (err: any) {
      setShotGenerationStatus('failed');
      message.error(err?.response?.data?.detail || err?.message || '智能分镜生成失败');
    }
  }, [scenes, characters, pollShotStatus]);

  // 组件卸载时清理轮询定时器
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // 场景操作
  const handleAddScene = () => {
    const newScene: SceneItem = {
      id: scenes.length + 1,
      name: '新场景',
      description: '',
      type: '室内',
      environment: '',
      size: '中等',
      tags: [],
    };
    setEditingScene(newScene);
    setIsSceneModalOpen(true);
  };

  const handleEditScene = (scene: SceneItem) => {
    setEditingScene(scene);
    setIsSceneModalOpen(true);
  };

  const handleDeleteScene = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个场景吗？',
      onOk: () => {
        setScenes(scenes.filter(scene => scene.id !== id));
        message.success('场景已删除');
      },
    });
  };

  const handleSaveScene = (values: any) => {
    if (editingScene) {
      const updatedScene = { ...editingScene, ...values };
      if (editingScene.id) {
        setScenes(scenes.map(scene =>
          scene.id === editingScene.id ? updatedScene : scene
        ));
        message.success('场景已更新');
      } else {
        setScenes([...scenes, updatedScene]);
        message.success('场景已添加');
      }
      setIsSceneModalOpen(false);
      setEditingScene(null);
    }
  };

  // 角色操作
  const handleAddCharacter = () => {
    const newCharacter: CharacterItem = {
      id: characters.length + 1,
      name: '新角色',
      description: '',
      age: 25,
      gender: '男',
      occupation: '',
      personality: '',
      appearance: '',
      tags: [],
    };
    setEditingCharacter(newCharacter);
    setIsCharacterModalOpen(true);
  };

  const handleEditCharacter = (character: CharacterItem) => {
    setEditingCharacter(character);
    setIsCharacterModalOpen(true);
  };

  const handleDeleteCharacter = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个角色吗？',
      onOk: () => {
        setCharacters(characters.filter(char => char.id !== id));
        message.success('角色已删除');
      },
    });
  };

  const handleSaveCharacter = (values: any) => {
    if (editingCharacter) {
      const updatedCharacter = { ...editingCharacter, ...values };
      if (editingCharacter.id) {
        setCharacters(characters.map(char =>
          char.id === editingCharacter.id ? updatedCharacter : char
        ));
        message.success('角色已更新');
      } else {
        setCharacters([...characters, updatedCharacter]);
        message.success('角色已添加');
      }
      setIsCharacterModalOpen(false);
      setEditingCharacter(null);
    }
  };

  // 道具操作
  const handleAddProp = () => {
    const newProp: PropItem = {
      id: props.length + 1,
      name: '新道具',
      description: '',
      category: '家具',
      material: '',
      size: '小型',
      tags: [],
    };
    setEditingProp(newProp);
    setIsPropModalOpen(true);
  };

  const handleEditProp = (prop: PropItem) => {
    setEditingProp(prop);
    setIsPropModalOpen(true);
  };

  const handleDeleteProp = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个道具吗？',
      onOk: () => {
        setProps(props.filter(prop => prop.id !== id));
        message.success('道具已删除');
      },
    });
  };

  const handleSaveProp = (values: any) => {
    if (editingProp) {
      const updatedProp = { ...editingProp, ...values };
      if (editingProp.id) {
        setProps(props.map(prop =>
          prop.id === editingProp.id ? updatedProp : prop
        ));
        message.success('道具已更新');
      } else {
        setProps([...props, updatedProp]);
        message.success('道具已添加');
      }
      setIsPropModalOpen(false);
      setEditingProp(null);
    }
  };

  // 预览图像状态
  const [generatingPreview, setGeneratingPreview] = useState<Record<string, boolean>>({});
  const [previewImages, setPreviewImages] = useState<Record<string, string>>({});

  // 自动持久化：previewImages 变化时保存到 localStorage + pipeline state
  useEffect(() => {
    if (Object.keys(previewImages).length > 0) {
      localStorage.setItem('scene_preview_images', JSON.stringify(previewImages));

      // 构建 name → image_url 参考映射，供 Storyboard 视频生成使用
      const referenceImages = {
        characters: {} as Record<string, string>,
        scenes: {} as Record<string, string>,
        props: {} as Record<string, string>,
      };
      for (const [key, url] of Object.entries(previewImages)) {
        const parts = key.split('_');
        const type = parts[0];
        const id = parseInt(parts.slice(1).join('_'));
        if (type === 'character') {
          const ch = characters.find(c => c.id === id);
          if (ch?.name) referenceImages.characters[ch.name] = url;
        } else if (type === 'scene') {
          const sc = scenes.find(s => s.id === id);
          if (sc?.name) referenceImages.scenes[sc.name] = url;
        } else if (type === 'prop') {
          const pr = props.find(p => p.id === id);
          if (pr?.name) referenceImages.props[pr.name] = url;
        }
      }

      // 保存映射到 localStorage
      if (Object.keys(referenceImages.characters).length ||
          Object.keys(referenceImages.scenes).length) {
        localStorage.setItem('scene_reference_images', JSON.stringify(referenceImages));
      }

      // 异步保存到后端 pipeline state
      (async () => {
        const wId = getWorkId();
        if (!wId) return;
        try {
          const resp = await pipelineService.getPipelineState(wId);
          const existing = (resp as any)?.data || {};
          existing.referenceImages = referenceImages;
          existing.updatedAt = new Date().toISOString();
          await pipelineService.savePipelineState(wId, existing);
        } catch {}
      })();
    }
  }, [previewImages, scenes, characters, props, getWorkId]);

  // 预览图像生成
  const handlePreview = async (id: number, type: 'scene' | 'character' | 'prop', description: string) => {
    const key = `${type}_${id}`;
    if (generatingPreview[key]) return;

    setGeneratingPreview(prev => ({ ...prev, [key]: true }));
    try {
      const resp = await scriptService.generatePreviewImage({ description, category: type });
      if (!resp?.task_id) throw new Error('No task_id');

      // 轮询直到完成
      const poll = setInterval(async () => {
        try {
          const status = await scriptService.getPreviewImageStatus(resp.task_id);
          if (status?.status === 'completed' && status.image_url) {
            clearInterval(poll);
            setPreviewImages(prev => ({ ...prev, [key]: status.image_url! }));
            setGeneratingPreview(prev => ({ ...prev, [key]: false }));
            message.success('预览图已生成');
          } else if (status?.status === 'failed') {
            clearInterval(poll);
            setGeneratingPreview(prev => ({ ...prev, [key]: false }));
            message.error(status.error || '预览图生成失败');
          }
        } catch (e: any) {
          if (e?.response?.status === 404) {
            clearInterval(poll);
            setGeneratingPreview(prev => ({ ...prev, [key]: false }));
          }
        }
      }, 3000);
    } catch {
      setGeneratingPreview(prev => ({ ...prev, [key]: false }));
      message.error('预览图生成请求失败');
    }
  };

  // 构建预览描述
  const buildSceneDesc = (s: SceneItem) =>
    `${s.name}，${s.environment || ''}，${s.description || ''}，${s.type}场景`.replace(/，+/g, '，').replace(/^，|，$/g, '');
  const buildCharacterDesc = (c: CharacterItem) =>
    `${c.name}，${c.gender || ''}，${c.age ? c.age + '岁' : ''}，${c.occupation || ''}，${c.appearance || ''}，${c.description || ''}`.replace(/，+/g, '，').replace(/^，|，$/g, '');
  const buildPropDesc = (p: PropItem) =>
    `${p.name}，${p.category || ''}，${p.material || ''}，${p.description || ''}`.replace(/，+/g, '，').replace(/^，|，$/g, '');

  const renderScenes = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>场景库</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddScene}>
          添加场景
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {scenes.map((scene) => (
          <Col xs={24} sm={12} lg={12} key={scene.id}>
            <Card
              cover={previewImages[`scene_${scene.id}`] ? (
                <div style={{ height: 240, overflow: 'hidden', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <img src={previewImages[`scene_${scene.id}`]} alt={scene.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                </div>
              ) : undefined}
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditScene(scene)}>编辑</Button>,
                <Button key="preview" type="link" icon={<EyeOutlined />}
                  loading={generatingPreview[`scene_${scene.id}`]}
                  onClick={() => handlePreview(scene.id, 'scene', buildSceneDesc(scene))}>
                  {generatingPreview[`scene_${scene.id}`] ? '生成中' : '预览'}
                </Button>,
                <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteScene(scene.id)}>删除</Button>,
              ]}
            >
              <Card.Meta
                avatar={!previewImages[`scene_${scene.id}`] ? (
                  <Avatar style={{ backgroundColor: '#0066cc', fontSize: 18 }} icon={<EnvironmentOutlined />} />
                ) : undefined}
                title={<div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Text strong>{scene.name}</Text><Tag color="blue">{scene.type}</Tag>
                  <Space size={[2, 2]} wrap>{(scene.tags || []).map((t, i) => (<Tag key={i} color="default" style={{ fontSize: 11 }}>{t}</Tag>))}</Space>
                </div>}
                description={<Text type="secondary" style={{ fontSize: 12 }}>{scene.description}</Text>}
              />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  const renderCharacters = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>角色库</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddCharacter}>
          添加角色
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {characters.map((character) => (
          <Col xs={24} sm={12} lg={8} key={character.id}>
            <Card
              cover={previewImages[`character_${character.id}`] ? (
                <div style={{ height: 280, overflow: 'hidden', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <img src={previewImages[`character_${character.id}`]} alt={character.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top' }} />
                </div>
              ) : undefined}
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditCharacter(character)}>编辑</Button>,
                <Button key="preview" type="link" icon={<EyeOutlined />}
                  loading={generatingPreview[`character_${character.id}`]}
                  onClick={() => handlePreview(character.id, 'character', buildCharacterDesc(character))}>
                  {generatingPreview[`character_${character.id}`] ? '生成中' : '预览'}
                </Button>,
                <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteCharacter(character.id)}>删除</Button>,
              ]}
            >
              <Card.Meta
                avatar={!previewImages[`character_${character.id}`] ? (
                  <Avatar style={{ backgroundColor: character.gender === '男' ? '#0066cc' : '#ff3b30', fontSize: 18 }} icon={<TeamOutlined />} />
                ) : undefined}
                title={<div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Text strong>{character.name}</Text>
                  <Tag color={character.gender === '男' ? 'blue' : 'pink'}>{character.gender}</Tag>
                  <Tag>{character.age}岁</Tag>
                  <Space size={[2, 2]} wrap>{character.tags.map((t, i) => (<Tag key={i} color="default" style={{ fontSize: 11 }}>{t}</Tag>))}</Space>
                </div>}
                description={<Text type="secondary" style={{ fontSize: 12 }}>{character.description}</Text>}
              />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  const renderProps = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>道具库</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddProp}>
          添加道具
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {props.map((prop) => (
          <Col xs={24} sm={12} lg={8} key={prop.id}>
            <Card
              cover={previewImages[`prop_${prop.id}`] ? (
                <div style={{ height: 240, overflow: 'hidden', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <img src={previewImages[`prop_${prop.id}`]} alt={prop.name}
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                </div>
              ) : undefined}
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditProp(prop)}>编辑</Button>,
                <Button key="preview" type="link" icon={<EyeOutlined />}
                  loading={generatingPreview[`prop_${prop.id}`]}
                  onClick={() => handlePreview(prop.id, 'prop', buildPropDesc(prop))}>
                  {generatingPreview[`prop_${prop.id}`] ? '生成中' : '预览'}
                </Button>,
                <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteProp(prop.id)}>删除</Button>,
              ]}
            >
              <Card.Meta
                avatar={!previewImages[`prop_${prop.id}`] ? (
                  <Avatar style={{ backgroundColor: '#34c759', fontSize: 18 }} icon={<ToolOutlined />} />
                ) : undefined}
                title={<div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Text strong>{prop.name}</Text><Tag color="green">{prop.category}</Tag>
                  <Space size={[2, 2]} wrap>{prop.tags.map((t, i) => (<Tag key={i} color="default" style={{ fontSize: 11 }}>{t}</Tag>))}</Space>
                </div>}
                description={<Text type="secondary" style={{ fontSize: 12 }}>{prop.description}</Text>}
              />
            </Card>
          </Col>
        ))}
      </Row>
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
            <TeamOutlined style={{ marginRight: 8 }} />
            场景角色道具
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>管理场景、角色和道具资源库</Text>
        </div>
        <Button
          type="primary"
          size="middle"
          icon={<CameraOutlined />}
          onClick={handleSmartShotDivision}
          loading={shotGenerationStatus === 'generating'}
          disabled={shotGenerationStatus === 'generating'}
        >
          智能分镜
        </Button>
      </div>

      {/* 智能分镜进度指示 */}
      {shotGenerationStatus === 'generating' && (
        <div style={{
          padding: '8px 24px', background: '#f0f7ff', borderBottom: '1px solid #d6e4ff',
          textAlign: 'center',
        }}>
          <Progress percent={shotGenerationProgress} status="active" size="small" style={{ maxWidth: 400 }} />
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            <LoadingOutlined style={{ marginRight: 6 }} />
            AI 正在分析剧本并划分镜头...
          </Text>
        </div>
      )}
      {shotGenerationStatus === 'failed' && (
        <div style={{
          padding: '8px 24px', background: '#fff2f0', borderBottom: '1px solid #ffccc7',
          textAlign: 'center',
        }}>
          <Text type="danger" style={{ fontSize: 12 }}>智能分镜生成失败</Text>
          <Button size="small" type="link" onClick={handleSmartShotDivision}>重试</Button>
        </div>
      )}

      {/* 内容区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
        <Card>
          <div style={{ marginBottom: 24 }}>
            <Space>
              <Button
                type={activeTab === 'scenes' ? 'primary' : 'default'}
                icon={<EnvironmentOutlined />}
                onClick={() => setActiveTab('scenes')}
              >
                场景库
              </Button>
              <Button
                type={activeTab === 'characters' ? 'primary' : 'default'}
                icon={<TeamOutlined />}
                onClick={() => setActiveTab('characters')}
              >
                角色库
              </Button>
              <Button
                type={activeTab === 'props' ? 'primary' : 'default'}
                icon={<ToolOutlined />}
                onClick={() => setActiveTab('props')}
              >
                道具库
              </Button>
            </Space>
          </div>

          <div style={{ marginTop: 24 }}>
            {activeTab === 'scenes' && renderScenes()}
            {activeTab === 'characters' && renderCharacters()}
            {activeTab === 'props' && renderProps()}
          </div>
        </Card>
      </div>

      {/* 场景编辑模态框 */}
      <Modal
        title={editingScene?.id ? '编辑场景' : '添加场景'}
        open={isSceneModalOpen}
        onCancel={() => {
          setIsSceneModalOpen(false);
          setEditingScene(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveScene}
          initialValues={editingScene || {}}
        >
          <Form.Item
            label="场景名称"
            name="name"
            rules={[{ required: true, message: '请输入场景名称' }]}
          >
            <Input placeholder="例如：现代咖啡馆" />
          </Form.Item>
          <Form.Item
            label="场景描述"
            name="description"
          >
            <TextArea rows={3} placeholder="描述场景的特点和用途" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="场景类型"
                name="type"
                rules={[{ required: true, message: '请选择场景类型' }]}
              >
                <Select>
                  <Option value="室内">室内</Option>
                  <Option value="室外">室外</Option>
                  <Option value="虚拟">虚拟</Option>
                  <Option value="混合">混合</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="场景大小"
                name="size"
              >
                <Select>
                  <Option value="小型">小型</Option>
                  <Option value="中等">中等</Option>
                  <Option value="大型">大型</Option>
                  <Option value="超大">超大</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="环境描述"
            name="environment"
          >
            <Input placeholder="例如：温馨、明亮、舒适" />
          </Form.Item>
          <Form.Item
            label="标签"
            name="tags"
          >
            <Select mode="tags" placeholder="输入标签，按回车添加" />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {(form) => {
              const desc = form.getFieldValue('description') || '';
              const env = form.getFieldValue('environment') || '';
              const tags = form.getFieldValue('tags') || [];
              const name = form.getFieldValue('name') || '';
              const type = form.getFieldValue('type') || '';
              const prompt = `一个场景环境图，${name}${type ? '（' + type + '）' : ''}，${desc}，${env}。${tags.length ? '标签：' + tags.join('、') + '。' : ''}风格：写实，宽屏构图，高质量，适合短剧场景设定。`;
              return (
                <Form.Item label={<span style={{ color: '#0066cc' }}>🎬 生成提示词预览</span>}>
                  <TextArea rows={4} value={prompt} readOnly style={{ background: '#f8f9fa', color: '#555', fontSize: 12, fontFamily: 'monospace' }} />
                </Form.Item>
              );
            }}
          </Form.Item>
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsSceneModalOpen(false);
                setEditingScene(null);
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

      {/* 角色编辑模态框 */}
      <Modal
        title={editingCharacter?.id ? '编辑角色' : '添加角色'}
        open={isCharacterModalOpen}
        onCancel={() => {
          setIsCharacterModalOpen(false);
          setEditingCharacter(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveCharacter}
          initialValues={editingCharacter || {}}
        >
          <Form.Item
            label="角色名称"
            name="name"
            rules={[{ required: true, message: '请输入角色名称' }]}
          >
            <Input placeholder="例如：商务男士" />
          </Form.Item>
          <Form.Item
            label="角色描述"
            name="description"
          >
            <TextArea rows={3} placeholder="描述角色的特点和背景" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                label="年龄"
                name="age"
                rules={[{ required: true, message: '请输入年龄' }]}
              >
                <InputNumber min={1} max={120} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="性别"
                name="gender"
              >
                <Select>
                  <Option value="男">男</Option>
                  <Option value="女">女</Option>
                  <Option value="其他">其他</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                label="职业"
                name="occupation"
              >
                <Input placeholder="例如：企业高管" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="性格特点"
            name="personality"
          >
            <Input placeholder="例如：稳重、理性、果断" />
          </Form.Item>
          <Form.Item
            label="外貌特征"
            name="appearance"
          >
            <Input placeholder="例如：西装革履，戴眼镜" />
          </Form.Item>
          <Form.Item
            label="标签"
            name="tags"
          >
            <Select mode="tags" placeholder="输入标签，按回车添加" />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {(form) => {
              const name = form.getFieldValue('name') || '';
              const desc = form.getFieldValue('description') || '';
              const gender = form.getFieldValue('gender') || '';
              const age = form.getFieldValue('age') || '';
              const occupation = form.getFieldValue('occupation') || '';
              const appearance = form.getFieldValue('appearance') || '';
              const personality = form.getFieldValue('personality') || '';
              const tags = form.getFieldValue('tags') || [];
              const charDesc = `${name}，${gender}，${age}岁${occupation ? '，' + occupation : ''}。${desc}。外貌：${appearance}。性格：${personality}`;
              const prompt = `专业角色设计参考图，"${name}"，${charDesc}。${tags.length ? '标签：' + tags.join('、') + '。' : ''}三视图，表情设定，纯白背景，角色独立于白色背景上，电影级写实风格，超高清，高质量，细节丰富。`;
              return (
                <Form.Item label={<span style={{ color: '#0066cc' }}>🎬 生成提示词预览</span>}>
                  <TextArea rows={5} value={prompt} readOnly style={{ background: '#f8f9fa', color: '#555', fontSize: 12, fontFamily: 'monospace' }} />
                </Form.Item>
              );
            }}
          </Form.Item>
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsCharacterModalOpen(false);
                setEditingCharacter(null);
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

      {/* 道具编辑模态框 */}
      <Modal
        title={editingProp?.id ? '编辑道具' : '添加道具'}
        open={isPropModalOpen}
        onCancel={() => {
          setIsPropModalOpen(false);
          setEditingProp(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          layout="vertical"
          onFinish={handleSaveProp}
          initialValues={editingProp || {}}
        >
          <Form.Item
            label="道具名称"
            name="name"
            rules={[{ required: true, message: '请输入道具名称' }]}
          >
            <Input placeholder="例如：笔记本电脑" />
          </Form.Item>
          <Form.Item
            label="道具描述"
            name="description"
          >
            <TextArea rows={3} placeholder="描述道具的特点和用途" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="道具分类"
                name="category"
              >
                <Select>
                  <Option value="家具">家具</Option>
                  <Option value="电子产品">电子产品</Option>
                  <Option value="装饰品">装饰品</Option>
                  <Option value="武器">武器</Option>
                  <Option value="交通工具">交通工具</Option>
                  <Option value="其他">其他</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="道具大小"
                name="size"
              >
                <Select>
                  <Option value="小型">小型</Option>
                  <Option value="中等">中等</Option>
                  <Option value="大型">大型</Option>
                  <Option value="超大">超大</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="材质"
            name="material"
          >
            <Input placeholder="例如：金属、塑料" />
          </Form.Item>
          <Form.Item
            label="标签"
            name="tags"
          >
            <Select mode="tags" placeholder="输入标签，按回车添加" />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {(form) => {
              const name = form.getFieldValue('name') || '';
              const desc = form.getFieldValue('description') || '';
              const category = form.getFieldValue('category') || '';
              const material = form.getFieldValue('material') || '';
              const size = form.getFieldValue('size') || '';
              const tags = form.getFieldValue('tags') || [];
              const prompt = `一件道具的展示图，${name}${category ? '（' + category + '）' : ''}，${desc}。材质：${material || '未指定'}，大小：${size || '未指定'}。${tags.length ? '标签：' + tags.join('、') + '。' : ''}风格：写实，白底产品图，高质量，细节清晰。`;
              return (
                <Form.Item label={<span style={{ color: '#0066cc' }}>🎬 生成提示词预览</span>}>
                  <TextArea rows={4} value={prompt} readOnly style={{ background: '#f8f9fa', color: '#555', fontSize: 12, fontFamily: 'monospace' }} />
                </Form.Item>
              );
            }}
          </Form.Item>
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsPropModalOpen(false);
                setEditingProp(null);
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
    </div>
  );
};

export default Scene;
