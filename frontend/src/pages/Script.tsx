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

const Script: React.FC = () => {
  const [activeTab, setActiveTab] = useState('scenes');
  const [scenes, setScenes] = useState<Scene[]>([
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
  ]);

  const [characters, setCharacters] = useState<Character[]>([
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
  ]);

  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [isSceneModalOpen, setIsSceneModalOpen] = useState(false);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState(false);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);

  // 场景操作
  const handleAddScene = () => {
    const newScene: Scene = {
      id: scenes.length + 1,
      title: '新场景',
      description: '',
      location: '',
      timeOfDay: '白天',
      characters: [],
      content: '',
      order: scenes.length + 1,
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
        setScenes(scenes.filter(scene => scene.id !== id));
        message.success('场景已删除');
      },
    });
  };

  const handleSaveScene = (values: any) => {
    if (editingScene) {
      const updatedScene = { ...editingScene, ...values };
      if (editingScene.id) {
        // 更新现有场景
        setScenes(scenes.map(scene =>
          scene.id === editingScene.id ? updatedScene : scene
        ));
        message.success('场景已更新');
      } else {
        // 添加新场景
        setScenes([...scenes, updatedScene]);
        message.success('场景已添加');
      }
      setIsSceneModalOpen(false);
      setEditingScene(null);
    }
  };

  // 角色操作
  const handleAddCharacter = () => {
    const newCharacter: Character = {
      id: characters.length + 1,
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

  const renderScenes = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>场景列表</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddScene}>
          添加场景
        </Button>
      </div>

      <List
        dataSource={scenes}
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
    </div>
  );

  const renderCharacters = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4}>角色管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddCharacter}>
          添加角色
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {characters.map((character) => (
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
    </div>
  );

  const renderOutline = () => (
    <div>
      <Title level={4}>剧本大纲</Title>
      <TextArea
        placeholder="在这里编写剧本大纲..."
        rows={12}
        style={{ marginBottom: 16 }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Text type="secondary">总字数：{scenes.reduce((total, scene) => total + scene.content.length, 0)} 字</Text>
        <Button type="primary" icon={<SaveOutlined />}>保存大纲</Button>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <FileTextOutlined style={{ marginRight: 12 }} />
          故事剧本
        </Title>
        <Text type="secondary">创建和管理您的剧本内容，包括场景、角色和剧情</Text>
      </div>

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="场景管理" key="scenes" />
          <TabPane tab="角色管理" key="characters" />
          <TabPane tab="剧本大纲" key="outline" />
        </Tabs>

        <div style={{ marginTop: 24 }}>
          {activeTab === 'scenes' && renderScenes()}
          {activeTab === 'characters' && renderCharacters()}
          {activeTab === 'outline' && renderOutline()}
        </div>
      </Card>

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
                <Select>
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
                <Select>
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
            <Select>
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
    </div>
  );
};

export default Script;