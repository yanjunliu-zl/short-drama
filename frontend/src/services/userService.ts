import { api } from '@/api/axios'
import type {
  User,
  UserProfile,
  UpdateUserRequest,
  UpdateUserProfileRequest,
  PaginatedResponse,
  ApiResponse,
} from '@/types'

export const userService = {
  // 获取用户列表
  getUsers: async (params: {
    page?: number
    pageSize?: number
    keyword?: string
  }): Promise<ApiResponse<PaginatedResponse<User>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<User>>>('/v1/users', { params })
    return response.data
  },

  // 获取单个用户
  getUser: async (userId: number): Promise<ApiResponse<User>> => {
    const response = await api.get<ApiResponse<User>>(`/v1/users/${userId}`)
    return response.data
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<ApiResponse<User>> => {
    const response = await api.get<ApiResponse<User>>('/v1/users/me')
    return response.data
  },

  // 更新用户信息
  updateUser: async (userId: number, data: UpdateUserRequest): Promise<ApiResponse<User>> => {
    const response = await api.put<ApiResponse<User>>(`/v1/users/${userId}`, data)
    return response.data
  },

  // 删除用户
  deleteUser: async (userId: number): Promise<ApiResponse<void>> => {
    const response = await api.delete<ApiResponse<void>>(`/v1/users/${userId}`)
    return response.data
  },

  // 获取用户资料
  getUserProfile: async (userId: number): Promise<ApiResponse<UserProfile>> => {
    const response = await api.get<ApiResponse<UserProfile>>(`/v1/users/${userId}/profile`)
    return response.data
  },

  // 更新用户资料
  updateUserProfile: async (userId: number, data: UpdateUserProfileRequest): Promise<ApiResponse<UserProfile>> => {
    const response = await api.put<ApiResponse<UserProfile>>(`/v1/users/${userId}/profile`, data)
    return response.data
  },

  // 上传用户头像
  uploadAvatar: async (userId: number, file: File): Promise<ApiResponse<{ avatar_url: string }>> => {
    const formData = new FormData()
    formData.append('avatar', file)

    const response = await api.post<ApiResponse<{ avatar_url: string }>>(
      `/v1/users/${userId}/avatar`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return response.data
  },

  // 更改密码
  changePassword: async (
    userId: number,
    currentPassword: string,
    newPassword: string
  ): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>(`/v1/users/${userId}/change-password`, {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return response.data
  },

  // 检查用户名是否可用
  checkUsernameAvailability: async (username: string): Promise<ApiResponse<{ available: boolean }>> => {
    const response = await api.get<ApiResponse<{ available: boolean }>>('/v1/users/check-username', {
      params: { username },
    })
    return response.data
  },

  // 检查邮箱是否可用
  checkEmailAvailability: async (email: string): Promise<ApiResponse<{ available: boolean }>> => {
    const response = await api.get<ApiResponse<{ available: boolean }>>('/v1/users/check-email', {
      params: { email },
    })
    return response.data
  },
}