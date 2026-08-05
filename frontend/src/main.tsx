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

// 主题配置 — 微软/苹果风格
const theme = {
  token: {
    colorPrimary: '#0066cc',
    colorSuccess: '#34c759',
    colorWarning: '#ff9500',
    colorError: '#ff3b30',
    colorInfo: '#007aff',
    colorBgBase: '#ffffff',
    colorBgContainer: '#ffffff',
    colorBgLayout: '#f5f5f7',
    colorTextBase: '#1d1d1f',
    colorTextSecondary: '#86868b',
    colorTextTertiary: '#aeaeb2',
    colorTextQuaternary: '#aeaeb2',
    colorBorder: '#e5e5ea',
    colorBorderSecondary: '#e5e5ea',
    borderRadius: 8,
    fontSize: 14,
    colorLink: '#0066cc',
    colorLinkHover: '#0052a3',
    colorLinkActive: '#003d7a',
    wireframe: false,
    controlItemBgHover: '#f2f2f7',
    colorBgTextHover: '#f2f2f7',
    colorBgTextActive: '#e8e8ed',
    colorFillAlter: '#f5f5f7',
    colorFillSecondary: '#f5f5f7',
    colorSplit: '#e5e5ea',
  },
  components: {
    Button: {
      borderRadius: 6,
      colorPrimary: '#0066cc',
      colorPrimaryHover: '#0052a3',
      colorPrimaryActive: '#003d7a',
      primaryShadow: '0 1px 3px rgba(0, 0, 0, 0.04)',
      defaultBg: '#ffffff',
      defaultBorderColor: '#e5e5ea',
      defaultColor: '#1d1d1f',
      defaultHoverBg: '#f5f5f7',
      defaultHoverBorderColor: '#d2d2d7',
      defaultHoverColor: '#0066cc',
      defaultActiveBg: '#f2f2f7',
      defaultActiveBorderColor: '#d2d2d7',
      defaultActiveColor: '#0052a3',
      fontWeight: 500,
      paddingInline: 20,
      paddingBlock: 6,
    },
    Card: {
      borderRadiusLG: 12,
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#e5e5ea',
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.04)',
      boxShadowTertiary: '0 2px 8px rgba(0, 0, 0, 0.04), 0 4px 16px rgba(0, 0, 0, 0.04)',
      colorTextHeading: '#1d1d1f',
      colorTextDescription: '#86868b',
      paddingLG: 24,
    },
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#f5f5f7',
      bodyBg: '#ffffff',
      triggerBg: '#f5f5f7',
      triggerColor: '#86868b',
      headerHeight: 48,
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: '#e8e8ed',
      itemColor: '#86868b',
      itemSelectedColor: '#0066cc',
      itemHoverBg: '#f2f2f7',
      itemHoverColor: '#1d1d1f',
      itemActiveBg: '#e8e8ed',
      horizontalItemSelectedColor: '#0066cc',
      iconSize: 16,
      collapsedIconSize: 16,
      itemHeight: 40,
      itemBorderRadius: 6,
    },
    Input: {
      colorBgContainer: '#ffffff',
      colorBorder: '#e5e5ea',
      colorText: '#1d1d1f',
      colorTextPlaceholder: '#aeaeb2',
      activeBorderColor: '#0066cc',
      hoverBorderColor: '#d2d2d7',
      activeShadow: '0 0 0 2px rgba(0, 102, 204, 0.1)',
      borderRadius: 8,
      paddingInline: 12,
      paddingBlock: 8,
    },
    Select: {
      colorBgContainer: '#ffffff',
      colorBorder: '#e5e5ea',
      colorText: '#1d1d1f',
      colorTextPlaceholder: '#aeaeb2',
      optionSelectedBg: '#f0f7ff',
      optionSelectedColor: '#0066cc',
      optionActiveBg: '#f2f2f7',
    },
    Table: {
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#e5e5ea',
      headerBg: '#f5f5f7',
      headerColor: '#1d1d1f',
      headerSplitColor: '#e5e5ea',
      rowHoverBg: '#f2f2f7',
      rowSelectedBg: '#f0f7ff',
      bodySortBg: '#f5f5f7',
      borderColor: '#e5e5ea',
      cellPaddingBlock: 12,
      cellPaddingInline: 16,
    },
    Tabs: {
      itemColor: '#86868b',
      itemHoverColor: '#0066cc',
      itemSelectedColor: '#0066cc',
      itemActiveColor: '#0066cc',
      inkBarColor: '#0066cc',
      colorBorderSecondary: '#e5e5ea',
    },
    Modal: {
      colorBgElevated: '#ffffff',
      colorBorder: '#e5e5ea',
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06), 0 8px 32px rgba(0, 0, 0, 0.06)',
      titleColor: '#1d1d1f',
      borderRadiusLG: 12,
    },
    Typography: {
      colorText: '#1d1d1f',
      colorTextSecondary: '#86868b',
      colorTextHeading: '#1d1d1f',
      titleMarginBottom: '0.5em',
    },
    Tag: {
      borderRadiusSM: 4,
    },
    Avatar: {
      colorTextPlaceholder: '#ffffff',
    },
    Dropdown: {
      colorBgElevated: '#ffffff',
      boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.08)',
    },
    Tooltip: {
      colorBgSpotlight: '#1d1d1f',
      colorTextLightSolid: '#ffffff',
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
