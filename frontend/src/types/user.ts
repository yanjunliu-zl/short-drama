export interface User {
  id: number
  username: string
  email: string
  phone?: string
  avatar?: string
  status: UserStatus
  role: UserRole
  last_login_at?: string
  created_at: string
  updated_at: string
}

export interface UserProfile {
  user_id: number
  full_name?: string
  gender: Gender
  birthday?: string
  bio?: string
  website?: string
  social_links?: string
  created_at: string
  updated_at: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  phone?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  id: number
  username: string
  email: string
  token: string
  refresh_token: string
  expires_at: string
}

export interface UpdateUserRequest {
  username?: string
  email?: string
  phone?: string
  avatar?: string
}

export interface UpdateUserProfileRequest {
  full_name?: string
  gender?: Gender
  birthday?: string
  bio?: string
  website?: string
  social_links?: string
}

export interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

// 枚举类型
export enum UserStatus {
  Inactive = 0,
  Active = 1,
  Suspended = 2,
}

export enum UserRole {
  User = 0,
  Admin = 1,
  SuperAdmin = 2,
}

export enum Gender {
  Unknown = 0,
  Male = 1,
  Female = 2,
}

export type { ApiResponse, PaginatedResponse } from './common'

