import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { store } from '@/store'
import { clearAuth, refreshToken } from '@/store/slices/authSlice'
import { notification } from 'antd'

// 创建axios实例
const axiosInstance: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000, // 30秒超时
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
axiosInstance.interceptors.request.use(
  (config) => {
    const state = store.getState()
    const token = state.auth.token

    // 添加认证token
    if (token) {
      config.headers = config.headers || {}
      ;(config.headers as any).Authorization = `Bearer ${token}`
    }

    // 添加请求时间戳
    config.headers = config.headers || {}
    ;(config.headers as any)['X-Request-Timestamp'] = Date.now().toString()

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    // 处理成功的响应
    const { data } = response

    // 如果后端返回特定的成功格式
    if (data && typeof data === 'object') {
      if (data.code && data.code !== 200) {
        // 业务错误
        const errorMessage = data.message || data.error || '请求失败'
        notification.error({
          message: '操作失败',
          description: errorMessage,
          duration: 3,
        })
        return Promise.reject(new Error(errorMessage))
      }
    }

    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 处理401错误（token过期）
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        // 尝试刷新token
        await store.dispatch(refreshToken())
        const state = store.getState()
        const newToken = state.auth.token

        // 更新请求头并重试
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return axiosInstance(originalRequest)
      } catch (refreshError) {
        // 刷新token失败，清除认证状态
        store.dispatch(clearAuth())
        notification.error({
          message: '会话过期',
          description: '请重新登录',
          duration: 3,
        })

        // 重定向到登录页
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    // 处理其他错误
    const { response } = error
    let errorMessage = '网络错误，请稍后重试'

    if (response) {
      const { status, data } = response

      switch (status) {
        case 400:
          errorMessage = data?.message || '请求参数错误'
          break
        case 403:
          errorMessage = '权限不足，无法访问此资源'
          break
        case 404:
          errorMessage = '请求的资源不存在'
          break
        case 409:
          errorMessage = data?.message || '资源冲突'
          break
        case 422:
          errorMessage = data?.message || '数据验证失败'
          break
        case 429:
          errorMessage = '请求过于频繁，请稍后重试'
          break
        case 500:
          errorMessage = '服务器内部错误'
          break
        case 502:
        case 503:
        case 504:
          errorMessage = '服务暂时不可用，请稍后重试'
          break
        default:
          errorMessage = data?.message || `请求失败 (${status})`
      }
    } else if (error.request) {
      // 请求已发出但没有收到响应
      errorMessage = '网络连接错误，请检查网络设置'
    } else {
      // 请求配置错误
      errorMessage = error.message || '请求配置错误'
    }

    // 显示错误通知（非401错误）
    if (error.response?.status !== 401) {
      notification.error({
        message: '请求失败',
        description: errorMessage,
        duration: 5,
      })
    }

    return Promise.reject(error)
  }
)

// 导出封装的请求方法
export const api = {
  get: <T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    axiosInstance.get(url, config),

  post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    axiosInstance.post(url, data, config),

  put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    axiosInstance.put(url, data, config),

  patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    axiosInstance.patch(url, data, config),

  delete: <T = any>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<T>> =>
    axiosInstance.delete(url, config),
}

export default axiosInstance