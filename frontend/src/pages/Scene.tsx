import React, { useState } from 'react';
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
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  TeamOutlined,
  EnvironmentOutlined,
  ToolOutlined,
} from '@ant-design/icons';

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
  const [activeTab, setActiveTab] = useState('scenes');
  const [scenes, setScenes] = useState<SceneItem[]>([
    {
      id: 1,
      name: '现代咖啡馆',
      description: '温馨的现代风格咖啡馆，适合对话场景',
      type: '室内',
      environment: '温馨、明亮、舒适',
      size: '中等',
      tags: ['现代', '咖啡', '休闲'],
    },
    {
      id: 2,
      name: '森林小径',
      description: '清晨的森林小径，阳光透过树叶洒落',
      type: '室外',
      environment: '自然、清新、宁静',
      size: '大型',
      tags: ['自然', '森林', '户外'],
    },
    {
      id: 3,
      name: '科技实验室',
      description: '充满未来科技感的实验室',
      type: '室内',
      environment: '科技、冷色调、专业',
      size: '中等',
      tags: ['科幻', '科技', '实验室'],
    },
  ]);

  const [characters, setCharacters] = useState<CharacterItem[]>([
    {
      id: 1,
      name: '商务男士',
      description: '成熟稳重的商务人士形象',
      age: 35,
      gender: '男',
      occupation: '企业高管',
      personality: '稳重、理性、果断',
      appearance: '西装革履，戴眼镜',
      tags: ['商务', '成熟', '专业'],
    },
    {
      id: 2,
      name: '学生少女',
      description: '活泼开朗的学生形象',
      age: 18,
      gender: '女',
      occupation: '学生',
      personality: '活泼、开朗、好奇',
      appearance: '校服，马尾辫',
      tags: ['学生', '青春', '活泼'],
    },
    {
      id: 3,
      name: '老爷爷',
      description: '和蔼可亲的老人形象',
      age: 70,
      gender: '男',
      occupation: '退休教师',
      personality: '和蔼、智慧、耐心',
      appearance: '花白头发，戴老花镜',
      tags: ['老人', '智慧', '和蔼'],
    },
  ]);

  const [props, setProps] = useState<PropItem[]>([
    {
      id: 1,
      name: '笔记本电脑',
      description: '现代轻薄笔记本电脑',
      category: '电子产品',
      material: '金属、塑料',
      size: '小型',
      tags: ['科技', '办公', '现代'],
    },
    {
      id: 2,
      name: '古典沙发',
      description: '欧式古典风格沙发',
      category: '家具',
      material: '实木、布料',
      size: '大型',
      tags: ['古典', '家具', '舒适'],
    },
    {
      id: 3,
      name: '魔法书',
      description: '古老的神秘魔法书',
      category: '装饰品',
      material: '皮革、纸张',
      size: '小型',
      tags: ['魔法', '神秘', '古老'],
    },
  ]);

  const [editingScene, setEditingScene] = useState<SceneItem | null>(null);
  const [editingCharacter, setEditingCharacter] = useState<CharacterItem | null>(null);
  const [editingProp, setEditingProp] = useState<PropItem | null>(null);
  const [isSceneModalOpen, setIsSceneModalOpen] = useState(false);
  const [isCharacterModalOpen, setIsCharacterModalOpen] = useState(false);
  const [isPropModalOpen, setIsPropModalOpen] = useState(false);

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
          <Col xs={24} sm={12} lg={8} key={scene.id}>
            <Card
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
              <Card.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: '#1890ff',
                      fontSize: 20,
                    }}
                  >
                    <EnvironmentOutlined />
                  </Avatar>
                }
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text strong>{scene.name}</Text>
                    <Tag color="blue">{scene.type}</Tag>
                  </div>
                }
                description={
                  <div>
                    <div style={{ marginBottom: 8 }}>{scene.description}</div>
                    <div><Text strong>环境：</Text>{scene.environment}</div>
                    <div><Text strong>大小：</Text>{scene.size}</div>
                    <div style={{ marginTop: 8 }}>
                      <Space size={[4, 4]} wrap>
                        {scene.tags.map((tag, index) => (
                          <Tag key={index} color="default">{tag}</Tag>
                        ))}
                      </Space>
                    </div>
                  </div>
                }
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
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditCharacter(character)}>
                  编辑
                </Button>,
                <Button key="preview" type="link" icon={<EyeOutlined />}>
                  预览
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
                      backgroundColor: character.gender === '男' ? '#1890ff' : '#f759ab',
                      fontSize: 20,
                    }}
                  >
                    <TeamOutlined />
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
                    <div style={{ marginBottom: 8 }}>{character.description}</div>
                    <div><Text strong>年龄：</Text>{character.age}岁</div>
                    <div><Text strong>职业：</Text>{character.occupation}</div>
                    <div><Text strong>性格：</Text>{character.personality}</div>
                    <div><Text strong>外貌：</Text>{character.appearance}</div>
                    <div style={{ marginTop: 8 }}>
                      <Space size={[4, 4]} wrap>
                        {character.tags.map((tag, index) => (
                          <Tag key={index} color="default">{tag}</Tag>
                        ))}
                      </Space>
                    </div>
                  </div>
                }
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
              actions={[
                <Button key="edit" type="link" icon={<EditOutlined />} onClick={() => handleEditProp(prop)}>
                  编辑
                </Button>,
                <Button key="preview" type="link" icon={<EyeOutlined />}>
                  预览
                </Button>,
                <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDeleteProp(prop.id)}>
                  删除
                </Button>,
              ]}
            >
              <Card.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: '#52c41a',
                      fontSize: 20,
                    }}
                  >
                    <ToolOutlined />
                  </Avatar>
                }
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text strong>{prop.name}</Text>
                    <Tag color="green">{prop.category}</Tag>
                  </div>
                }
                description={
                  <div>
                    <div style={{ marginBottom: 8 }}>{prop.description}</div>
                    <div><Text strong>材质：</Text>{prop.material}</div>
                    <div><Text strong>大小：</Text>{prop.size}</div>
                    <div style={{ marginTop: 8 }}>
                      <Space size={[4, 4]} wrap>
                        {prop.tags.map((tag, index) => (
                          <Tag key={index} color="default">{tag}</Tag>
                        ))}
                      </Space>
                    </div>
                  </div>
                }
              />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <TeamOutlined style={{ marginRight: 12 }} />
          场景角色道具
        </Title>
        <Text type="secondary">管理您的场景、角色和道具资源库</Text>
      </div>

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
