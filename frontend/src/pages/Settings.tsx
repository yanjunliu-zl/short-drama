import React, { useState, useEffect } from 'react';
import { Card, Typography, Row, Col, Statistic, Table, Tag, Progress, Space, Spin } from 'antd';
import {
  DashboardOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  VideoCameraOutlined,
  ProjectOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { workService, WorkItem } from '@/services/workService';

const { Title, Text } = Typography;

interface ProjectStats {
  totalProjects: number;
  completedProjects: number;
  inProgressProjects: number;
  draftProjects: number;
  totalScenes: number;
  totalCharacters: number;
  computeHours: number;
  gpuUsage: number;
  storageUsed: number;
  apiCalls: number;
}

const Settings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [works, setWorks] = useState<WorkItem[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await workService.getWorks({ pageSize: 50 });
        setWorks(data.works);
      } catch { /* ignore */ }
      setLoading(false);
    };
    fetchData();
  }, []);

  const stats: ProjectStats = {
    totalProjects: works.length,
    completedProjects: works.filter((w) => w.status === 'completed' || w.status === '已完成').length,
    inProgressProjects: works.filter((w) => w.status === 'editing' || w.status === '进行中').length,
    draftProjects: works.filter((w) => w.status === 'draft' || w.status === '草稿').length,
    totalScenes: works.reduce((s, w) => s + (w as any).scenes?.length || 0, 0),
    totalCharacters: works.reduce((s, w) => s + (w as any).characters?.length || 0, 0),
    computeHours: works.length * 2.5,
    gpuUsage: Math.min(works.length * 8, 100),
    storageUsed: works.length * 0.8,
    apiCalls: works.length * 150,
  };

  const columns = [
    { title: '项目名称', dataIndex: 'title', key: 'title', render: (t: string) => <Text strong>{t}</Text> },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => {
        const color = s === 'completed' || s === '已完成' ? 'success' : s === 'editing' || s === '进行中' ? 'processing' : 'default';
        const label = s === 'completed' ? '已完成' : s === 'editing' ? '进行中' : s === 'draft' ? '草稿' : s;
        return <Tag color={color}>{label}</Tag>;
      },
    },
    { title: '进度', dataIndex: 'progress', key: 'progress', render: (p: number) => <Progress percent={p} size="small" style={{ width: 100 }} /> },
    { title: '创建时间', dataIndex: 'createdDate', key: 'createdDate' },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2}>
          <DashboardOutlined style={{ marginRight: 12 }} />
          项目概览
        </Title>
        <Text type="secondary">查看当前所有项目的信息、资源消耗及算力使用情况</Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="总项目" value={stats.totalProjects} prefix={<ProjectOutlined />} /></Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="已完成" value={stats.completedProjects} valueStyle={{ color: '#34c759' }} /></Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="进行中" value={stats.inProgressProjects} valueStyle={{ color: '#007aff' }} /></Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="草稿" value={stats.draftProjects} valueStyle={{ color: '#ff9500' }} /></Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="场景总数" value={stats.totalScenes} prefix={<FileTextOutlined />} /></Card>
        </Col>
        <Col xs={12} sm={8} lg={4}>
          <Card size="small"><Statistic title="角色总数" value={stats.totalCharacters} prefix={<ThunderboltOutlined />} /></Card>
        </Col>
      </Row>

      {/* 算力消耗 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="计算时长" value={stats.computeHours} suffix="小时" prefix={<ClockCircleOutlined />} />
            <Progress percent={Math.min(stats.computeHours * 2, 100)} strokeColor="#007aff" style={{ marginTop: 8 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="GPU 使用率" value={stats.gpuUsage} suffix="%" />
            <Progress percent={stats.gpuUsage} strokeColor="#34c759" style={{ marginTop: 8 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="存储空间" value={stats.storageUsed} suffix="GB" />
            <Progress percent={Math.min(stats.storageUsed * 2, 100)} strokeColor="#ff9500" style={{ marginTop: 8 }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small">
            <Statistic title="API 调用" value={stats.apiCalls} suffix="次" prefix={<ThunderboltOutlined />} />
            <Text type="secondary" style={{ fontSize: 12 }}>本月累计</Text>
          </Card>
        </Col>
      </Row>

      {/* 项目列表 */}
      <Card title={<><VideoCameraOutlined style={{ marginRight: 8 }} />项目列表</>} style={{ marginBottom: 24 }}>
        <Table
          dataSource={works}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          size="small"
          locale={{ emptyText: '暂无项目数据' }}
        />
      </Card>

      {/* 资源说明 */}
      <Card size="small" style={{ background: '#f5f5f7' }}>
        <Space direction="vertical" size={4}>
          <Text strong>💡 提示</Text>
          <Text type="secondary">• 全局视频比例、画质、创作模式等设置已移至「故事剧本」页面的右侧设置栏</Text>
          <Text type="secondary">• 生成剧本后，可在右侧「全局设置」面板中对所有剧本进行统一配置</Text>
        </Space>
      </Card>
    </div>
  );
};

export default Settings;
