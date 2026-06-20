import React, { useState, useEffect, useCallback } from 'react';
import { Tabs, Card, Typography, Row, Col, Button, Space, List, Avatar, Spin, Alert, Empty, Pagination, message } from 'antd';
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
import { caseService } from '@/services/caseService';
import type { CaseItem } from '@/types/case';
import { workService, WorkItem } from '@/services/workService';
import { assetService, AssetItem } from '@/services/assetService';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

const Home: React.FC = () => {
  const [activeTab, setActiveTab] = useState('case_square');

  // 案例广场数据状态
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize] = useState(6);
  const [tagFilter, setTagFilter] = useState<string>('');
  const [sortBy] = useState<'views' | 'likes' | 'createdAt'>('views');

  // 我的作品数据状态
  const [works, setWorks] = useState<WorkItem[]>([]);
  const [worksLoading, setWorksLoading] = useState(false);
  const [worksError, setWorksError] = useState<string | null>(null);

  // 个人资产数据状态
  const [personalAssets, setPersonalAssets] = useState<AssetItem[]>([]);
  const [personalLoading, setPersonalLoading] = useState(false);

  // 公司资产数据状态
  const [companyAssets, setCompanyAssets] = useState<AssetItem[]>([]);
  const [companyLoading, setCompanyLoading] = useState(false);

  // 获取案例列表
  const fetchCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await caseService.getCases({
        page,
        pageSize,
        tag: tagFilter || undefined,
        sortBy,
        order: 'desc',
      });
      setCases(data.cases);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || '获取案例列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, tagFilter, sortBy]);

  // 获取作品列表
  const fetchWorks = useCallback(async () => {
    setWorksLoading(true);
    setWorksError(null);
    try {
      const data = await workService.getWorks({ pageSize: 20 });
      setWorks(data.works);
    } catch (err: any) {
      setWorksError(err.message || '获取作品列表失败');
    } finally {
      setWorksLoading(false);
    }
  }, []);

  // 获取个人资产
  const fetchPersonalAssets = useCallback(async () => {
    setPersonalLoading(true);
    try {
      const data = await assetService.getPersonalAssets({ user_id: '1', pageSize: 20 });
      setPersonalAssets(data.assets);
    } catch {
      // 静默处理
    } finally {
      setPersonalLoading(false);
    }
  }, []);

  // 获取公司资产
  const fetchCompanyAssets = useCallback(async () => {
    setCompanyLoading(true);
    try {
      const data = await assetService.getCompanyAssets({ pageSize: 20 });
      setCompanyAssets(data.assets);
    } catch {
      // 静默处理
    } finally {
      setCompanyLoading(false);
    }
  }, []);

  // 标签页切换时加载数据
  useEffect(() => {
    switch (activeTab) {
      case 'case_square':
        fetchCases();
        break;
      case 'my_works':
        fetchWorks();
        break;
      case 'personal_assets':
        fetchPersonalAssets();
        break;
      case 'company_assets':
        fetchCompanyAssets();
        break;
    }
  }, [activeTab, fetchCases, fetchWorks, fetchPersonalAssets, fetchCompanyAssets]);

  const handleTabChange = (key: string) => {
    setActiveTab(key);
  };

  // 处理标签筛选
  const handleTagClick = (tag: string) => {
    setTagFilter(tag === tagFilter ? '' : tag);
    setPage(1);
  };

  // 处理点赞
  const handleLike = async (id: string) => {
    try {
      const result = await caseService.likeCase(id);
      setCases(prev =>
        prev.map(c => (c.id === id ? { ...c, likes: result.likes } : c))
      );
      message.success('点赞成功');
    } catch {
      message.error('点赞失败');
    }
  };

  // 处理浏览记录
  const handleView = async (id: string) => {
    try {
      await caseService.recordView(id);
    } catch {
      // 静默处理浏览记录错误
    }
  };

  // 处理分享
  const handleShare = async (id: string) => {
    try {
      await caseService.recordShare(id);
      message.success('分享成功');
    } catch {
      message.error('分享失败');
    }
  };

  // 渲染案例广场内容
  const renderCaseSquare = () => (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={3}>案例广场</Title>
        <Text type="secondary">浏览平台上的优秀创作案例，获取灵感</Text>
      </div>

      {/* 标签筛选 */}
      {!loading && !error && (
        <div style={{ marginBottom: 16 }}>
          <Space wrap>
            {['科幻', '古风', '悬疑', '奇幻', '职场', '家庭'].map(tag => (
              <Button
                key={tag}
                type={tagFilter === tag ? 'primary' : 'default'}
                size="small"
                onClick={() => handleTagClick(tag)}
              >
                {tag}
              </Button>
            ))}
            {tagFilter && (
              <Button size="small" onClick={() => setTagFilter('')}>
                清除筛选
              </Button>
            )}
          </Space>
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" tip="加载案例中..." />
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <Alert
          message="加载失败"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchCases}>
              重试
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 空状态 */}
      {!loading && !error && cases.length === 0 && (
        <Empty description="暂无案例" style={{ padding: 80 }} />
      )}

      {/* 案例卡片列表 */}
      {!loading && !error && cases.length > 0 && (
        <>
          <Row gutter={[24, 24]}>
            {cases.map((item) => (
              <Col xs={24} sm={12} lg={8} key={item.id}>
                <Card
                  hoverable
                  cover={
                    <div
                      style={{
                        height: 160,
                        backgroundColor: item.coverColor ? `#${item.coverColor}` : '#0066cc',
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
                    <Space
                      key="view"
                      onClick={() => handleView(item.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <EyeOutlined />
                      <span>{item.views}</span>
                    </Space>,
                    <Space
                      key="like"
                      onClick={() => handleLike(item.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <LikeOutlined />
                      <span>{item.likes}</span>
                    </Space>,
                    <div
                      key="share"
                      onClick={() => handleShare(item.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <ShareAltOutlined />
                    </div>
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
                                  backgroundColor: tagFilter === tag ? '#0066cc' : '#e5e5ea',
                                  color: tagFilter === tag ? '#fff' : 'inherit',
                                  borderRadius: 4,
                                  fontSize: 12,
                                  cursor: 'pointer'
                                }}
                                onClick={() => handleTagClick(tag)}
                              >
                                {tag}
                              </span>
                            ))}
                          </Space>
                        </div>
                        <div style={{ marginTop: 12, fontSize: 12, color: '#86868b' }}>
                          作者：{item.author}
                        </div>
                      </div>
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>

          {/* 分页 */}
          {total > pageSize && (
            <div style={{ textAlign: 'center', marginTop: 24 }}>
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={(p) => setPage(p)}
                showSizeChanger={false}
                showTotal={(t) => `共 ${t} 个案例`}
              />
            </div>
          )}
        </>
      )}
    </div>
  );

  // Map status from backend to display text
  const statusMap: Record<string, { text: string; color: string }> = {
    completed: { text: '已完成', color: '#34c759' },
    editing: { text: '进行中', color: '#0066cc' },
    draft: { text: '草稿', color: '#ff9500' },
  };

  // 渲染我的作品内容
  const renderMyWorks = () => (
    <div>
      <div style={{ marginBottom: 0 }}>
        <Title level={3}>我的作品</Title>
        <Text type="secondary">管理您的创作项目，查看进度和状态</Text>
      </div>

      {worksLoading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
        </div>
      )}

      {worksError && (
        <Alert message="加载失败" description={worksError} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      {!worksLoading && !worksError && works.length === 0 && (
        <Empty description="暂无作品" style={{ padding: 80 }} />
      )}

      {!worksLoading && !worksError && works.length > 0 && (
        <Card>
          <List
            itemLayout="horizontal"
            dataSource={works}
            renderItem={(item) => {
              const st = statusMap[item.status] || { text: item.status, color: '#86868b' };
              return (
                <List.Item
                  actions={[
                    <Button key="edit" type="link">编辑</Button>,
                    <Button key="preview" type="link">预览</Button>,
                    <Button key="export" type="link" icon={<DownloadOutlined />}>导出</Button>
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <Avatar style={{ backgroundColor: st.color }}>
                        {item.title.substring(0, 1)}
                      </Avatar>
                    }
                    title={
                      <div>
                        <Text strong>{item.title}</Text>
                        <span style={{ marginLeft: 12, fontSize: 12, padding: '2px 8px', backgroundColor: '#f5f5f7', borderRadius: 4 }}>
                          {item.type || '短剧'}
                        </span>
                      </div>
                    }
                    description={
                      <div>
                        <div>状态：<Text style={{ color: st.color }}>{st.text}</Text></div>
                        <div>创建时间：{item.createdDate} | 最后修改：{item.lastModified}</div>
                        {item.status !== 'completed' && (
                          <div style={{ marginTop: 8 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ width: '100%', height: 6, backgroundColor: '#f5f5f7', borderRadius: 3 }}>
                                  <div
                                    style={{
                                      width: `${item.progress}%`,
                                      height: '100%',
                                      backgroundColor: '#0066cc',
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
              );
            }}
          />
        </Card>
      )}

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

      {personalLoading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
        </div>
      )}

      {!personalLoading && personalAssets.length === 0 && (
        <Empty description="暂无个人资产" style={{ padding: 80 }} />
      )}

      {!personalLoading && personalAssets.length > 0 && (
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
                    <Avatar style={{ backgroundColor: '#0066cc', fontSize: 20 }}>
                      {asset.name.substring(0, 1)}
                    </Avatar>
                  }
                  title={
                    <div>
                      <Text strong>{asset.name}</Text>
                      <span style={{ marginLeft: 12, fontSize: 12, color: '#86868b' }}>
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
      )}

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

      {companyLoading && (
        <div style={{ textAlign: 'center', padding: 80 }}>
          <Spin size="large" />
        </div>
      )}

      {!companyLoading && companyAssets.length === 0 && (
        <Empty description="暂无公司资产" style={{ padding: 80 }} />
      )}

      {!companyLoading && companyAssets.length > 0 && (
        <Card>
          <List
            dataSource={companyAssets}
            renderItem={(asset) => (
              <List.Item
                actions={[
                  <Button key="access" type="link">{asset.accessLevel || '全体员工'}</Button>,
                  <Button key="use" type="link">使用</Button>,
                  <Button key="details" type="link">详情</Button>
                ]}
              >
                <List.Item.Meta
                  avatar={
                    <Avatar style={{ backgroundColor: '#0066cc', fontSize: 20 }}>
                      {asset.name.substring(0, 1)}
                    </Avatar>
                  }
                  title={
                    <div>
                      <Text strong>{asset.name}</Text>
                      <span style={{ marginLeft: 12, fontSize: 12, color: '#86868b' }}>
                        {asset.count} 项资源
                      </span>
                    </div>
                  }
                  description={
                    <div>
                      <div>资源类型：{asset.type}</div>
                      <div>访问权限：<Text type="secondary">{asset.accessLevel || '全体员工'}</Text></div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Card>
      )}

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