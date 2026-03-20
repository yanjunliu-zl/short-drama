import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import './styles/global.css'

import App from './App'
import { store, persistor } from './store'
import { Provider } from 'react-redux'
import { PersistGate } from 'redux-persist/integration/react'

// 设置dayjs本地化
dayjs.locale('zh-cn')

// 主题配置
const theme = {
  token: {
    colorPrimary: '#0080ff',
    colorSuccess: '#00e6b8',
    colorWarning: '#ffaa00',
    colorError: '#ff3366',
    colorInfo: '#667fff',
    colorBgBase: '#e5e7eb', // rgb(229,231,235)
    colorTextBase: '#1f2937',
    colorTextSecondary: '#6b7280',
    borderRadius: 8,
    fontSize: 14,
    colorLink: '#00c6ff',
    wireframe: false,
  },
  components: {
    Button: {
      borderRadius: 6,
      colorPrimary: '#0080ff',
      colorPrimaryHover: '#00c6ff',
      colorPrimaryActive: '#0066cc',
    },
    Card: {
      borderRadiusLG: 12,
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#d1d5db',
    },
    Layout: {
      headerBg: '#e5e7eb',
      siderBg: '#e5e7eb',
      bodyBg: '#e5e7eb',
      triggerBg: '#d1d5db',
      triggerColor: '#6b7280',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: '#d1d5db',
      itemColor: '#6b7280',
      itemSelectedColor: '#1f2937',
    },
    Input: {
      colorBgContainer: '#ffffff',
      colorBorder: '#d1d5db',
      colorText: '#1f2937',
      colorTextPlaceholder: '#9ca3af',
    },
    Select: {
      colorBgContainer: '#ffffff',
      colorBorder: '#d1d5db',
      colorText: '#1f2937',
    },
    Table: {
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#d1d5db',
      headerBg: '#f3f4f6',
      headerColor: '#1f2937',
      rowHoverBg: '#f3f4f6',
    },
  },
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Provider store={store}>
      <PersistGate loading={null} persistor={persistor}>
        <ConfigProvider locale={zhCN} theme={theme}>
          <App />
        </ConfigProvider>
      </PersistGate>
    </Provider>
  </React.StrictMode>
)