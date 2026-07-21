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
  LockOutlined,
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
    '/settings': 'settings_page',
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
    // 需要登录的页面：未登录时跳转到登录页
    const protectedPages = ['story_script', 'scene_character_props', 'storyboard_script', 'storyboard_video', 'final_video'];
    if (protectedPages.includes(key) && !isAuthenticated) {
      navigate('/login', { state: { from: route } });
      return;
    }
    // 为故事剧本/场景/分镜/视频/成片页面携带当前 workId
    if (protectedPages.includes(key)) {
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
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
      onClick: () => navigate('/settings'),
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
        trigger={
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            width: '100%',
            fontSize: 10,
            color: '#86868b',
            lineHeight: 1,
          }}>
            {collapsed ? '▶' : '◀'}
          </div>
        }
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
          .ant-layout-sider-trigger {
            height: 24px !important;
            line-height: 24px !important;
            background: #f5f5f7 !important;
            border-top: 1px solid #e5e5ea !important;
            padding: 0 !important;
          }
          .ant-layout-sider-trigger:hover {
            background: #e8e8ed !important;
          }
          .ant-layout-sider-trigger > * {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
          }
          .sidebar-user-area .ant-avatar {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            vertical-align: middle !important;
          }
          .sidebar-user-area .ant-avatar > .anticon {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            vertical-align: unset !important;
            line-height: 1 !important;
          }
          .sidebar-user-area .ant-avatar > .anticon svg {
            display: block !important;
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

        {/* 侧边栏底部用户区域 — 与顶部 Logo 统一布局 */}
        <div
          className="sidebar-user-area"
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            borderTop: '1px solid #e5e5ea',
            background: '#f5f5f7',
            flexShrink: 0,
          }}
        >
          {isAuthenticated ? (
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                cursor: 'pointer',
              }}>
                <Avatar
                  size={collapsed ? 26 : 30}
                  icon={<UserOutlined />}
                  style={{ backgroundColor: '#0066cc', flexShrink: 0 }}
                />
                {!collapsed && (
                  <span style={{ fontSize: 14, fontWeight: 500, color: '#1d1d1f' }}>
                    {user?.username || '用户'}
                  </span>
                )}
              </div>
            </Dropdown>
          ) : (
            collapsed ? (
              <Button type="primary" shape="circle" size="small" icon={<LoginOutlined />} onClick={() => navigate('/login')} />
            ) : (
              <div style={{ display: 'flex', gap: 8, width: '100%' }}>
                <Button type="primary" icon={<LoginOutlined />} onClick={() => navigate('/login')} block size="middle">登录</Button>
                <Button onClick={() => navigate('/register')} block size="middle">注册</Button>
              </div>
            )
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