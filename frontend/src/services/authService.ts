import { api } from '@/api/axios'
import type { LoginRequest, RegisterRequest, LoginResponse, ApiResponse } from '@/types'

export const authService = {
  // 用户登录
  login: async (credentials: LoginRequest): Promise<ApiResponse<LoginResponse>> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/v1/users/login', credentials)
    return response.data
  },

  // 用户注册
  register: async (userData: RegisterRequest): Promise<ApiResponse<LoginResponse>> => {
    const response = await api.post<ApiResponse<LoginResponse>>('/v1/users/register', userData)
    return response.data
  },

  // 用户登出
  logout: async (): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>('/v1/users/logout')
    return response.data
  },

  // 刷新token
  refreshToken: async (refreshToken: string): Promise<ApiResponse<{ token: string; refresh_token: string }>> => {
    const response = await api.post<ApiResponse<{ token: string; refresh_token: string }>>(
      '/v1/users/refresh-token',
      { refresh_token: refreshToken }
    )
    return response.data
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<ApiResponse<any>> => {
    const response = await api.get<ApiResponse<any>>('/v1/users/me')
    return response.data
  },

  // 发送重置密码邮件
  sendResetPasswordEmail: async (email: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>('/v1/users/reset-password', { email })
    return response.data
  },

  // 重置密码
  resetPassword: async (token: string, newPassword: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>('/v1/users/reset-password/confirm', {
      token,
      new_password: newPassword,
    })
    return response.data
  },

  // 验证token
  verifyToken: async (token: string): Promise<ApiResponse<{ valid: boolean }>> => {
    const response = await api.post<ApiResponse<{ valid: boolean }>>('/v1/users/verify-token', { token })
    return response.data
  },
}