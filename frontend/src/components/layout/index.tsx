import React, { ReactNode } from 'react';
import { Layout as AntLayout, Menu } from 'antd';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  FileTextOutlined,
  TeamOutlined,
  CameraOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  SettingOutlined
} from '@ant-design/icons';

const { Sider, Content } = AntLayout;

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = React.useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // 路由到菜单key的映射
  const routeMap: Record<string, string> = {
    '/overview': 'overview',
    '/script': 'story_script',
    '/scene': 'scene_character_props',
    '/storyboard': 'storyboard_script',
    '/video': 'storyboard_video',
    '/final-cut': 'final_video',
    // 首页 '/' 没有对应的菜单项
  };

  // 菜单key到路由的映射
  const menuKeyToRoute: Record<string, string> = {
    'overview': '/overview',
    'story_script': '/script',
    'scene_character_props': '/scene',
    'storyboard_script': '/storyboard',
    'storyboard_video': '/video',
    'final_video': '/final-cut',
  };

  // 获取当前选中的菜单key
  const getSelectedKey = () => {
    return routeMap[location.pathname] || 'overview';
  };

  // 菜单项点击处理
  const handleMenuClick = ({ key }: { key: string }) => {
    const route = menuKeyToRoute[key] || '/';
    navigate(route);
  };

  // 导航菜单项
  const menuItems = [
    {
      key: 'overview',
      icon: <SettingOutlined />,
      label: '概览',
    },
    {
      key: 'story_script',
      icon: <FileTextOutlined />,
      label: '故事剧本',
    },
    {
      key: 'scene_character_props',
      icon: <TeamOutlined />,
      label: '场景角色道具',
    },
    {
      key: 'storyboard_script',
      icon: <CameraOutlined />,
      label: '分镜脚本',
    },
    {
      key: 'storyboard_video',
      icon: <PlayCircleOutlined />,
      label: '分镜视频',
    },
    {
      key: 'final_video',
      icon: <EyeOutlined />,
      label: '成片',
    },
  ];

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={250}
        style={{
          background: '#e5e7eb',
          borderRight: '1px solid #d1d5db',
        }}
      >
        <Link to="/" style={{ textDecoration: 'none' }}>
          <div style={{
            height: '64px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid #d1d5db',
            background: '#e5e7eb',
            cursor: 'pointer'
          }}>
            {!collapsed ? (
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#0080ff' }}>
                拓扑漫剧
              </div>
            ) : (
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#0080ff' }}>
                T
              </div>
            )}
          </div>
        </Link>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderRight: 'none', background: 'transparent', marginTop: '16px' }}
        />
      </Sider>
      <AntLayout>
        <Content
          style={{
            padding: 0,
            margin: 0,
            minHeight: 'calc(100vh - 0px)',
            background: '#e5e7eb',
          }}
        >
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;