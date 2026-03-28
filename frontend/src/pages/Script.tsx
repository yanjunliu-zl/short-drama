import React, { useState } from 'react';
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
} from 'antd';
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
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

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
  role: string; // 主角、配角、反派等
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

const Script: React.FC = () => {
  // 初始化默认数据
  const initialScenes: Scene[] = [
    {
      id: 1,
      title: '开场 - 相遇',
      description: '男女主角在咖啡馆初次相遇',
      location: '城市咖啡馆',
      timeOfDay: '下午',
      characters: ['李明', '张薇'],
      content: '李明走进咖啡馆，四处张望。张薇坐在角落，专注地看着手中的书。',
      order: 1,
    },
    {
      id: 2,
      title: '对话 - 自我介绍',
      description: '两人开始交谈，互相了解',
      location: '咖啡馆内',
      timeOfDay: '下午',
      characters: ['李明', '张薇'],
      content: '李明：你好，我能坐这里吗？\n张薇：请坐。你也喜欢这本书吗？',
      order: 2,
    },
    {
      id: 3,
      title: '冲突 - 误会',
      description: '男主角的朋友出现引发误会',
      location: '咖啡馆门口',
      timeOfDay: '傍晚',
      characters: ['李明', '张薇', '王强'],
      content: '王强突然出现，误会两人的关系。张薇尴尬地解释。',
      order: 3,
    },
  ];

  const initialCharacters: Character[] = [
    {
      id: 1,
      name: '李明',
      description: '软件工程师，性格内向但善良',
      age: 28,
      gender: '男',
      role: '主角',
    },
    {
      id: 2,
      name: '张薇',
      description: '作家，独立自主的女性',
      age: 26,
      gender: '女',
      role: '主角',
    },
    {
      id: 3,
      name: '王强',
      description: '李明的朋友，性格直爽',
      age: 29,
      gender: '男',
      role: '配角',
    },
  ];

  // 多集数据状态
  const [episodes, setEpisodes] = useState<Episode[]>([
    {
      id: 'ep-1',
      title: '第一集',
      number: 1,
      scenes: initialScenes,
      characters: initialCharacters,
      description: '故事的开端，主角相遇',
    },
  ]);

  // 当前激活的集数
  const [activeEpisodeId, setActiveEpisodeId] = useState<string>('ep-1');

  // 当前标签页
  const [activeTab, setActiveTab] = useState('scenes');

  // 当前编辑的场景和角色
  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [isSceneModalOpen, setIsSceneModalOpen] = useState(false);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);

  // 抽屉状态
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<Episode | null>(null);

  // 获取当前集数的数据
  const currentEpisode = episodes.find(ep => ep.id === activeEpisodeId);
  const currentScenes = currentEpisode?.scenes || [];
  const currentCharacters = currentEpisode?.characters || [];

  // 集数操作
  const handleAddEpisode = () => {
    const newEpisode: Episode = {
      id: `ep-${Date.now()}`,
      title: `第${episodes.length + 1}集`,
      number: episodes.length + 1,
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

  // 场景操作
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
      const updatedScenes = currentScenes.map(scene =>
        scene.id === updatedScene.id ? updatedScene : scene
      );

      if (!editingScene.id) {
        // 添加新场景
        updatedScenes.push(updatedScene);
      }

      updateEpisodeScenes(updatedScenes);
      setIsSceneModalOpen(false);
      setEditingScene(null);
    }
  };

  // 角色操作
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
      const updatedCharacters = currentCharacters.map(char =>
        char.id === updatedCharacter.id ? updatedCharacter : char
      );

      if (!editingCharacter.id) {
        // 添加新角色
        updatedCharacters.push(updatedCharacter);
      }

      updateEpisodeCharacters(updatedCharacters);
      setIsCharacterModalOpen(false);
      setEditingCharacter(null);
    }
  };

  // 更新当前集数的场景和角色
  const updateEpisodeScenes = (scenes: Scene[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, scenes } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  const updateEpisodeCharacters = (characters: Character[]) => {
    if (currentEpisode) {
      const updatedEpisodes = episodes.map(ep =>
        ep.id === currentEpisode.id ? { ...ep, characters } : ep
      );
      setEpisodes(updatedEpisodes);
    }
  };

  // 渲染场景列表
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

                <div style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                  <Text strong>场景内容：</Text>
                  <div style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>{scene.content}</div>
                </div>
              </div>
            </div>
          </Card>
        )}
      />
      {currentScenes.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <FileTextOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无场景，点击"添加场景"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  // 渲染角色列表
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
                      backgroundColor: character.role === '主角' ? '#1890ff' :
                                      character.role === '配角' ? '#52c41a' : '#fa541c',
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
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <UserOutlined style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }} />
          <p>暂无角色，点击"添加角色"按钮开始创建</p>
        </div>
      )}
    </div>
  );

  // 渲染大纲
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

  // 渲染集数列表
  const renderEpisodeList = () => (
    <div style={{ borderRight: '1px solid #f0f0f0', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
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
              backgroundColor: activeEpisodeId === episode.id ? '#e6f7ff' : 'transparent',
              borderBottom: '1px solid #f0f0f0',
              transition: 'background-color 0.2s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StarOutlined
                  style={{
                    color: activeEpisodeId === episode.id ? '#1890ff' : '#d9d9d9',
                    fontSize: 16
                  }}
                />
                <Text strong style={{ color: activeEpisodeId === episode.id ? '#1890ff' : undefined }}>
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

      <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
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
    <div style={{ padding: '24px', height: 'calc(100vh - 120px)', display: 'flex' }}>
      {/* 左侧集数列表 */}
      <div style={{ width: 280, marginRight: 24, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        {renderEpisodeList()}
      </div>

      {/* 右侧内容区域 */}
      <div style={{ flex: 1, backgroundColor: '#fff', borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <Title level={2} style={{ margin: 0 }}>
                <FileTextOutlined style={{ marginRight: 12 }} />
                {currentEpisode?.title}
              </Title>
              <Text type="secondary">
                创建和管理您的剧本内容，包括场景、角色和剧情
              </Text>
            </div>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => message.info('预览功能开发中')}
            >
              预览本集
            </Button>
          </div>
        </div>

        <div style={{ padding: '24px', flex: 1 }}>
          <Tabs activeKey={activeTab} onChange={setActiveTab}>
            <TabPane tab="场景管理" key="scenes">
              {renderScenes()}
            </TabPane>
            <TabPane tab="角色管理" key="characters">
              {renderCharacters()}
            </TabPane>
            <TabPane tab="剧本大纲" key="outline">
              {renderOutline()}
            </TabPane>
          </Tabs>
        </div>
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
            label="场景标题"
            name="title"
            rules={[{ required: true, message: '请输入场景标题' }]}
          >
            <Input placeholder="例如：开场 - 相遇" />
          </Form.Item>
          <Form.Item
            label="场景描述"
            name="description"
          >
            <Input placeholder="简要描述这个场景的内容" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="地点"
                name="location"
                rules={[{ required: true, message: '请输入地点' }]}
              >
                <Input placeholder="例如：城市咖啡馆" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="时间"
                name="timeOfDay"
              >
                <Select placeholder="选择时间">
                  <Option value="早晨">早晨</Option>
                  <Option value="上午">上午</Option>
                  <Option value="中午">中午</Option>
                  <Option value="下午">下午</Option>
                  <Option value="傍晚">傍晚</Option>
                  <Option value="夜晚">夜晚</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="场景顺序"
            name="order"
          >
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            label="场景内容"
            name="content"
            rules={[{ required: true, message: '请输入场景内容' }]}
          >
            <TextArea rows={6} placeholder="详细描述场景内容，包括对话和动作" />
          </Form.Item>
          <Form.Item
            label="参与角色"
            name="characters"
          >
            <Select
              mode="tags"
              tokenSeparators={[',']}
              style={{ width: '100%' }}
              placeholder="输入角色名称，按回车确认"
              options={currentCharacters.map(char => ({
                value: char.name,
                label: char.name,
              }))}
            />
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
        width={500}
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
            <Input placeholder="例如：李明" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="年龄"
                name="age"
                rules={[{ required: true, message: '请输入年龄' }]}
              >
                <InputNumber min={1} max={120} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="性别"
                name="gender"
              >
                <Select placeholder="选择性别">
                  <Option value="男">男</Option>
                  <Option value="女">女</Option>
                  <Option value="其他">其他</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item
            label="角色类型"
            name="role"
          >
            <Select placeholder="选择角色类型">
              <Option value="主角">主角</Option>
              <Option value="配角">配角</Option>
              <Option value="反派">反派</Option>
              <Option value="群众">群众</Option>
            </Select>
          </Form.Item>
          <Form.Item
            label="角色描述"
            name="description"
          >
            <TextArea rows={4} placeholder="描述角色的性格、背景等信息" />
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

export default Script;
