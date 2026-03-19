import { Suspense, useEffect } from 'react'
import { BrowserRouter as Router } from 'react-router-dom'
import { Spin, notification } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

import AppRoutes from './routes'
import { useAuth } from './hooks/useAuth'
import Layout from './components/layout'

// 全局加载状态
const loadingIcon = <LoadingOutlined style={{ fontSize: 24 }} spin />

// AuthInitializer组件，用于在Router上下文内初始化认证
function AuthInitializer() {
  const { initializeAuth } = useAuth()

  useEffect(() => {
    // 初始化应用
    initializeAuth()

    // 全局错误处理
    const handleGlobalError = (event: ErrorEvent) => {
      console.error('全局错误:', event.error)
      notification.error({
        message: '应用错误',
        description: '发生了未知错误，请刷新页面重试',
        duration: 5,
      })
    }

    // 未处理的Promise rejection
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('未处理的Promise rejection:', event.reason)
      notification.error({
        message: '请求错误',
        description: event.reason?.message || '请求处理失败',
        duration: 5,
      })
    }

    window.addEventListener('error', handleGlobalError)
    window.addEventListener('unhandledrejection', handleUnhandledRejection)

    return () => {
      window.removeEventListener('error', handleGlobalError)
      window.removeEventListener('unhandledrejection', handleUnhandledRejection)
    }
  }, [initializeAuth])

  return null
}

function AppContent() {
  return (
    <Router>
      <AuthInitializer />
      <Layout>
        <Suspense
          fallback={
            <div className="flex items-center justify-center min-h-[400px]">
              <Spin indicator={loadingIcon} tip="加载中..." />
            </div>
          }
        >
          <AppRoutes />
        </Suspense>
      </Layout>
    </Router>
  )
}

function App() {
  return <AppContent />
}

export default App