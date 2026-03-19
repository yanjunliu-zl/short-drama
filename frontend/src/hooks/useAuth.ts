import { useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { notification } from 'antd'
import {
  login as loginAction,
  logout as logoutAction,
  register as registerAction,
  clearAuth,
  setError,
} from '@/store/slices/authSlice'
import { RootState } from '@/store'
import { LoginRequest, RegisterRequest } from '@/types'

export const useAuth = () => {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const authState = useSelector((state: RootState) => state.auth)
  const { user, token, isAuthenticated, isLoading, error } = authState

  const login = useCallback(
    async (credentials: LoginRequest) => {
      try {
        const result = await (dispatch as any)(loginAction(credentials)).unwrap()
        notification.success({
          message: '登录成功',
          description: `欢迎回来，${result.username}！`,
          duration: 2,
        })
        return result
      } catch (err: any) {
        notification.error({
          message: '登录失败',
          description: err.message || '请检查用户名和密码',
          duration: 3,
        })
        throw err
      }
    },
    [dispatch]
  )

  const register = useCallback(
    async (userData: RegisterRequest) => {
      try {
        const result = await (dispatch as any)(registerAction(userData)).unwrap()
        notification.success({
          message: '注册成功',
          description: '账户已创建，请登录',
          duration: 2,
        })
        return result
      } catch (err: any) {
        notification.error({
          message: '注册失败',
          description: err.message || '请检查输入信息',
          duration: 3,
        })
        throw err
      }
    },
    [dispatch]
  )

  const logout = useCallback(async () => {
    try {
      await (dispatch as any)(logoutAction()).unwrap()
      notification.success({
        message: '已登出',
        description: '您已成功登出',
        duration: 2,
      })
      navigate('/login')
    } catch (err: any) {
      notification.error({
        message: '登出失败',
        description: err.message || '请重试',
        duration: 3,
      })
    }
  }, [dispatch, navigate])

  const checkAuth = useCallback(() => {
    return isAuthenticated && !!token
  }, [isAuthenticated, token])

  const initializeAuth = useCallback(() => {
    // 检查token是否有效
    const token = localStorage.getItem('token')
    if (!token) {
      dispatch(clearAuth())
      return false
    }

    // 这里可以添加token验证逻辑
    return true
  }, [dispatch])

  const clearError = useCallback(() => {
    dispatch(setError(null))
  }, [dispatch])

  return {
    user,
    token,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    checkAuth,
    initializeAuth,
    clearError,
  }
}