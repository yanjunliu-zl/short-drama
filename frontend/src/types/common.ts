// 通用接口响应
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error?: string
  code?: number
  timestamp?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ListParams {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  keyword?: string
  [key: string]: any
}

// 分页配置
export interface PaginationConfig {
  current: number
  pageSize: number
  total: number
  showSizeChanger: boolean
  showQuickJumper: boolean
  showTotal: (total: number, range: [number, number]) => React.ReactNode
}

// 路由配置
export interface RouteConfig {
  path: string
  component: React.ComponentType
  exact?: boolean
  auth?: boolean
  roles?: string[]
  title?: string
  icon?: React.ReactNode
  children?: RouteConfig[]
}

// 菜单项
export interface MenuItem {
  key: string
  label: string
  icon?: React.ReactNode
  path?: string
  children?: MenuItem[]
  roles?: string[]
}

// 文件上传
export interface UploadFile {
  uid: string
  name: string
  status: 'uploading' | 'done' | 'error' | 'removed'
  url?: string
  size?: number
  type?: string
  response?: any
  error?: any
}

// 表单字段
export interface FormField {
  name: string
  label: string
  type: 'text' | 'number' | 'email' | 'password' | 'textarea' | 'select' | 'checkbox' | 'radio' | 'date' | 'time' | 'file'
  required?: boolean
  placeholder?: string
  options?: { label: string; value: any }[]
  rules?: any[]
  disabled?: boolean
  hidden?: boolean
}

// 通知消息
export interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: string
  read: boolean
  action?: {
    label: string
    onClick: () => void
  }
}

// 系统配置
export interface SystemConfig {
  site_name: string
  site_description: string
  site_keywords: string[]
  contact_email: string
  support_phone?: string
  social_links: {
    wechat?: string
    weibo?: string
    github?: string
    twitter?: string
    facebook?: string
  }
  features: {
    script_generation: boolean
    video_generation: boolean
    payment_enabled: boolean
    subscription_enabled: boolean
  }
  limits: {
    max_script_length: number
    max_video_duration: number
    max_file_size: number
    daily_script_limit: number
    daily_video_limit: number
  }
}

// 错误类型
export interface ApiError {
  code: number
  message: string
  details?: any
  timestamp?: string
}

// 加载状态
export interface LoadingState {
  isLoading: boolean
  error?: ApiError | null
}

// 搜索参数
export interface SearchParams {
  query: string
  filters: Record<string, any>
  sort: string
  order: 'asc' | 'desc'
}

// 图表数据
export interface ChartData {
  labels: string[]
  datasets: {
    label: string
    data: number[]
    backgroundColor?: string[]
    borderColor?: string
    borderWidth?: number
  }[]
}