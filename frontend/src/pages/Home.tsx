import React, { useState } from 'react';
import { Tabs, Card, Typography, Row, Col, Button, Space, List, Avatar } from 'antd';
import {
  AppstoreOutlined,
  FolderOutlined,
  UserOutlined,
  BankOutlined,
  EyeOutlined,
  DownloadOutlined,
  LikeOutlined,
  ShareAltOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

// 案例广场数据
const caseExamples = [
  {
    id: 1,
    title: '未来都市冒险',
    description: '一部关于未来科技与人性冲突的科幻短剧',
    author: 'AI创作助手',
    likes: 245,
    views: 1560,
    tags: ['科幻', '冒险', '未来'],
    coverColor: '#1890ff'
  },
  {
    id: 2,
    title: '古风爱情传奇',
    description: '古代宫廷中的爱恨情仇，精美的服化道设计',
    author: '传统编剧师',
    likes: 189,
    views: 980,
    tags: ['古风', '爱情', '历史'],
    coverColor: '#52c41a'
  },
  {
    id: 3,
    title: '悬疑推理剧场',
    description: '密室谋杀案的层层解谜，反转不断的剧情',
    author: '推理大师',
    likes: 312,
    views: 2100,
    tags: ['悬疑', '推理', '犯罪'],
    coverColor: '#fa8c16'
  },
  {
    id: 4,
    title: '奇幻魔法世界',
    description: '魔法学院的新生成长故事，奇幻生物与魔法对决',
    author: '奇幻作家',
    likes: 178,
    views: 1250,
    tags: ['奇幻', '魔法', '成长'],
    coverColor: '#722ed1'
  },
  {
    id: 5,
    title: '职场奋斗日记',
    description: '互联网公司的职场生存法则与团队协作',
    author: '职场观察员',
    likes: 156,
    views: 890,
    tags: ['职场', '励志', '都市'],
    coverColor: '#13c2c2'
  },
  {
    id: 6,
    title: '家庭温情小品',
    description: '普通家庭中的温馨日常与亲情故事',
    author: '生活记录者',
    likes: 198,
    views: 1100,
    tags: ['家庭', '温情', '生活'],
    coverColor: '#f759ab'
  }
];

// 我的作品数据
const myWorks = [
  {
    id: 1,
    title: '夏日海滩邂逅',
    status: '已完成',
    progress: 100,
    createdDate: '2026-03-15',
    lastModified: '2026-03-18',
    type: '爱情短剧'
  },
  {
    id: 2,
    title: '星际移民计划',
    status: '进行中',
    progress: 65,
    createdDate: '2026-03-10',
    lastModified: '2026-03-19',
    type: '科幻系列'
  },
  {
    id: 3,
    title: '侦探事务所',
    status: '草稿',
    progress: 30,
    createdDate: '2026-03-05',
    lastModified: '2026-03-12',
    type: '悬疑单元剧'
  }
];

// 个人资产数据
const personalAssets = [
  { id: 1, name: '角色模型库', count: 24, type: '3D模型', lastUpdate: '2026-03-18' },
  { id: 2, name: '场景素材包', count: 15, type: '场景资源', lastUpdate: '2026-03-16' },
  { id: 3, name: '音效库', count: 128, type: '音频资源', lastUpdate: '2026-03-15' },
  { id: 4, name: '特效模板', count: 42, type: '视觉特效', lastUpdate: '2026-03-14' },
  { id: 5, name: '对话模板', count: 56, type: '文本资源', lastUpdate: '2026-03-12' },
  { id: 6, name: '分镜模板', count: 18, type: '分镜资源', lastUpdate: '2026-03-10' }
];

// 公司资产数据
const companyAssets = [
  { id: 1, name: '企业角色库', count: 156, type: '3D模型', accessLevel: '全体员工' },
  { id: 2, name: '标准场景库', count: 89, type: '场景资源', accessLevel: '设计团队' },
  { id: 3, name: '官方音效库', count: 420, type: '音频资源', accessLevel: '全体员工' },
  { id: 4, name: '品牌素材包', count: 75, type: '视觉资源', accessLevel: '市场部' },
  { id: 5, name: '合规文本库', count: 203, type: '文本资源', accessLevel: '内容团队' },
  { id: 6, name: '分镜资源库', count: 67, type: '分镜资源', accessLevel: '导演团队' }
];

const Home: React.FC = () => {
  const [activeTab, setActiveTab] = useState('case_square');

  const handleTabChange = (key: string) => {
    setActiveTab(key);
  };

  // 渲染案例广场内容
  const renderCaseSquare = () => (
    <div>
      <div style={{ marginBottom: 0 }}>
        <Title level={3}>案例广场</Title>
        <Text type="secondary">浏览平台上的优秀创作案例，获取灵感</Text>
      </div>

      <Row gutter={[24, 24]}>
        {caseExamples.map((item) => (
          <Col xs={24} sm={12} lg={8} key={item.id}>
            <Card
              hoverable
              cover={
                <div
                  style={{
                    height: 160,
                    backgroundColor: item.coverColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: 20,
                    fontWeight: 'bold'
                  }}
                >
                  {item.title.substring(0, 4)}
                </div>
              }
              actions={[
                <Space key="view">
                  <EyeOutlined />
                  <span>{item.views}</span>
                </Space>,
                <Space key="like">
                  <LikeOutlined />
                  <span>{item.likes}</span>
                </Space>,
                <ShareAltOutlined key="share" />
              ]}
            >
              <Card.Meta
                title={item.title}
                description={
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {item.description}
                    </Text>
                    <div style={{ marginTop: 8 }}>
                      <Space size={[0, 8]} wrap>
                        {item.tags.map((tag, index) => (
                          <span
                            key={index}
                            style={{
                              padding: '2px 8px',
                              backgroundColor: '#d1d5db',
                              borderRadius: 4,
                              fontSize: 12
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </Space>
                    </div>
                    <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
                      作者：{item.author}
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

  // 渲染我的作品内容
  const renderMyWorks = () => (
    <div>
      <div style={{ marginBottom: 0 }}>
        <Title level={3}>我的作品</Title>
        <Text type="secondary">管理您的创作项目，查看进度和状态</Text>
      </div>

      <Card>
        <List
          itemLayout="horizontal"
          dataSource={myWorks}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button key="edit" type="link">编辑</Button>,
                <Button key="preview" type="link">预览</Button>,
                <Button key="export" type="link" icon={<DownloadOutlined />}>导出</Button>
              ]}
            >
              <List.Item.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: item.status === '已完成' ? '#52c41a' :
                                    item.status === '进行中' ? '#1890ff' : '#fa8c16'
                    }}
                  >
                    {item.title.substring(0, 1)}
                  </Avatar>
                }
                title={
                  <div>
                    <Text strong>{item.title}</Text>
                    <span style={{ marginLeft: 12, fontSize: 12, padding: '2px 8px', backgroundColor: '#f0f0f0', borderRadius: 4 }}>
                      {item.type}
                    </span>
                  </div>
                }
                description={
                  <div>
                    <div>状态：<Text type={item.status === '已完成' ? 'success' : item.status === '进行中' ? 'warning' : 'secondary'}>{item.status}</Text></div>
                    <div>创建时间：{item.createdDate} | 最后修改：{item.lastModified}</div>
                    {item.status !== '已完成' && (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ width: '100%', height: 6, backgroundColor: '#f0f0f0', borderRadius: 3 }}>
                              <div
                                style={{
                                  width: `${item.progress}%`,
                                  height: '100%',
                                  backgroundColor: '#1890ff',
                                  borderRadius: 3
                                }}
                              />
                            </div>
                          </div>
                          <Text style={{ fontSize: 12 }}>{item.progress}%</Text>
                        </div>
                      </div>
                    )}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <div style={{ marginTop: 24 }}>
        <Button type="primary" icon={<AppstoreOutlined />}>创建新作品</Button>
        <Button style={{ marginLeft: 12 }}>导入作品</Button>
        <Button style={{ marginLeft: 12 }} type="dashed">查看全部作品</Button>
      </div>
    </div>
  );

  // 渲染个人资产库内容
  const renderPersonalAssets = () => (
    <div>
      <div style={{ marginBottom: 0 }}>
        <Title level={3}>个人资产库</Title>
        <Text type="secondary">管理您的个人创作资源，包括模型、素材、音效等</Text>
      </div>

      <Row gutter={[24, 24]}>
        {personalAssets.map((asset) => (
          <Col xs={24} sm={12} lg={8} key={asset.id}>
            <Card
              hoverable
              actions={[
                <Button key="use" type="link">使用</Button>,
                <Button key="edit" type="link">编辑</Button>,
                <Button key="share" type="link">分享</Button>
              ]}
            >
              <Card.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: '#1890ff',
                      fontSize: 20
                    }}
                  >
                    {asset.name.substring(0, 1)}
                  </Avatar>
                }
                title={
                  <div>
                    <Text strong>{asset.name}</Text>
                    <span style={{ marginLeft: 12, fontSize: 12, color: '#666' }}>
                      {asset.count} 项
                    </span>
                  </div>
                }
                description={
                  <div>
                    <div>类型：{asset.type}</div>
                    <div>最后更新：{asset.lastUpdate}</div>
                  </div>
                }
              />
            </Card>
          </Col>
        ))}
      </Row>

      <div style={{ marginTop: 24 }}>
        <Space>
          <Button type="primary" icon={<FolderOutlined />}>上传新资产</Button>
          <Button>整理资产</Button>
          <Button>导出资产包</Button>
        </Space>
      </div>
    </div>
  );

  // 渲染公司资产库内容
  const renderCompanyAssets = () => (
    <div>
      <div style={{ marginBottom: 0 }}>
        <Title level={3}>公司资产库</Title>
        <Text type="secondary">访问公司共享的创作资源，提升团队协作效率</Text>
      </div>

      <Card>
        <List
          dataSource={companyAssets}
          renderItem={(asset) => (
            <List.Item
              actions={[
                <Button key="access" type="link">{asset.accessLevel}</Button>,
                <Button key="use" type="link">使用</Button>,
                <Button key="details" type="link">详情</Button>
              ]}
            >
              <List.Item.Meta
                avatar={
                  <Avatar
                    style={{
                      backgroundColor: '#722ed1',
                      fontSize: 20
                    }}
                  >
                    {asset.name.substring(0, 1)}
                  </Avatar>
                }
                title={
                  <div>
                    <Text strong>{asset.name}</Text>
                    <span style={{ marginLeft: 12, fontSize: 12, color: '#666' }}>
                      {asset.count} 项资源
                    </span>
                  </div>
                }
                description={
                  <div>
                    <div>资源类型：{asset.type}</div>
                    <div>访问权限：<Text type="secondary">{asset.accessLevel}</Text></div>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <div style={{ marginTop: 24 }}>
        <Text type="secondary">
          公司资产库由管理员统一维护，如需上传或修改资源请联系管理员
        </Text>
      </div>
    </div>
  );

  return (
    <div style={{ padding: '0' }}>
      <Card
        style={{ border: 'none', marginBottom: 0 }}
        styles={{ body: { padding: 0 } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          type="card"
          size="large"
        >
          <TabPane
            tab={
              <span>
                <AppstoreOutlined />
                案例广场
              </span>
            }
            key="case_square"
          />
          <TabPane
            tab={
              <span>
                <FolderOutlined />
                我的作品
              </span>
            }
            key="my_works"
          />
          <TabPane
            tab={
              <span>
                <UserOutlined />
                个人资产库
              </span>
            }
            key="personal_assets"
          />
          <TabPane
            tab={
              <span>
                <BankOutlined />
                公司资产库
              </span>
            }
            key="company_assets"
          />
        </Tabs>
      </Card>

      <Card style={{ border: 'none', background: 'transparent' }}>
        {activeTab === 'case_square' && renderCaseSquare()}
        {activeTab === 'my_works' && renderMyWorks()}
        {activeTab === 'personal_assets' && renderPersonalAssets()}
        {activeTab === 'company_assets' && renderCompanyAssets()}
      </Card>
    </div>
  );
};

export default Home;