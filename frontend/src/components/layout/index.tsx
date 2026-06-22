import React, { ReactNode } from 'react';
import { useSelector } from 'react-redux';
import type { RootState } from '@/store';
import { Layout as AntLayout, Menu, Button, Dropdown, Avatar } from 'antd';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import {
  FileTextOutlined,
  TeamOutlined,
  CameraOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  SettingOutlined,
  WalletOutlined,
  UserOutlined,
  LoginOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';

const { Sider, Content } = AntLayout;

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [collapsed, setCollapsed] = React.useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuth();
  const reduxUserId = useSelector((s: RootState) => (s.auth.user as any)?.id) || 'anonymous';

  // 路由到菜单key的映射
  const routeMap: Record<string, string> = {
    '/': 'overview',
    '/overview': 'overview',
    '/script': 'story_script',
    '/scene': 'scene_character_props',
    '/storyboard': 'storyboard_script',
    '/video': 'storyboard_video',
    '/final-cut': 'final_video',
    '/payment': 'payment_center',
  };

  // 菜单key到路由的映射
  const menuKeyToRoute: Record<string, string> = {
    'overview': '/',
    'story_script': '/script',
    'scene_character_props': '/scene',
    'storyboard_script': '/storyboard',
    'storyboard_video': '/video',
    'final_video': '/final-cut',
    'payment_center': '/payment',
  };

  // 获取当前选中的菜单key
  const getSelectedKey = () => {
    return routeMap[location.pathname] || 'overview';
  };

  // 菜单项点击处理
  const handleMenuClick = ({ key }: { key: string }) => {
    const route = menuKeyToRoute[key] || '/';
    // 为故事剧本/场景/分镜/视频/成片页面携带当前 workId
    const pipelinePages = ['story_script', 'scene_character_props', 'storyboard_script', 'storyboard_video', 'final_video'];
    if (pipelinePages.includes(key)) {
      const workId = localStorage.getItem(`pipeline_${reduxUserId}_workId`);
      navigate(workId ? `${route}?workId=${workId}` : route);
    } else {
      navigate(route);
    }
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

  // 用户下拉菜单
  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人中心',
      onClick: () => navigate('/'),
    },
    {
      key: 'payment',
      icon: <WalletOutlined />,
      label: '支付中心',
      onClick: () => navigate('/payment'),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => logout(),
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
          background: '#f5f5f7',
          borderRight: '1px solid #e5e5ea',
          height: '100vh',
          overflow: 'auto',
        }}
      >
        <style>{`
          .ant-layout-sider-children {
            display: flex !important;
            flex-direction: column !important;
            height: 100% !important;
          }
        `}</style>
        <Link to="/" style={{ textDecoration: 'none', flexShrink: 0 }}>
          <div style={{
            height: '64px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid #e5e5ea',
            background: '#f5f5f7',
            cursor: 'pointer'
          }}>
            {!collapsed ? (
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#0066cc' }}>
                拓扑漫剧
              </div>
            ) : (
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#0066cc' }}>
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
          style={{ borderRight: 'none', background: 'transparent', marginTop: '16px', flex: 1 }}
        />

        {/* 侧边栏底部用户区域 */}
        <div
          style={{
            padding: '16px',
            borderTop: '1px solid #e5e5ea',
            flexShrink: 0,
          }}
        >
          {isAuthenticated ? (
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px',
                  borderRadius: 8,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = '#f2f2f7'
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'transparent'
                }}
              >
                <Avatar
                  size={collapsed ? 28 : 32}
                  icon={<UserOutlined />}
                  style={{ backgroundColor: '#0066cc', flexShrink: 0 }}
                />
                {!collapsed && (
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: '#1d1d1f',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {user?.username || '用户'}
                    </div>
                    <div style={{ fontSize: 12, color: '#86868b' }}>
                      {user?.email || ''}
                    </div>
                  </div>
                )}
              </div>
            </Dropdown>
          ) : (
            <div style={{ display: 'flex', flexDirection: collapsed ? 'column' : 'row', gap: 8, alignItems: 'center' }}>
              <Button
                type="primary"
                icon={<LoginOutlined />}
                onClick={() => navigate('/login')}
                block
              >
                {!collapsed && '登录'}
              </Button>
              {!collapsed && (
                <Button
                  onClick={() => navigate('/register')}
                  block
                >
                  注册
                </Button>
              )}
            </div>
          )}
        </div>
      </Sider>
      <AntLayout>
        <Content
          style={{
            padding: 0,
            margin: 0,
            minHeight: '100vh',
            background: '#ffffff',
          }}
        >
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
};

export default Layout;