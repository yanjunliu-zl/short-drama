import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { LoginRequest, LoginResponse, User, RegisterRequest } from '@/types'
import { authService } from '@/services/authService'

/** Clear all pipeline_ prefixed localStorage keys on logout */
function clearPipelineStorage() {
  const keysToRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('pipeline_')) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach(key => localStorage.removeItem(key))
}

interface AuthState {
  user: User | null
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

const initialState: AuthState = {
  user: null,
  token: localStorage.getItem('token'),
  refreshToken: localStorage.getItem('refreshToken'),
  isAuthenticated: !!localStorage.getItem('token'),
  isLoading: false,
  error: null,
}

// Async thunks
export const login = createAsyncThunk<LoginResponse, LoginRequest>(
  'auth/login',
  async (credentials: LoginRequest, { rejectWithValue }) => {
    try {
      const response = await authService.login(credentials)
      if (response.success && response.data) {
        return response.data
      } else {
        return rejectWithValue(response.message || '登录失败')
      }
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const register = createAsyncThunk<LoginResponse, RegisterRequest>(
  'auth/register',
  async (userData: RegisterRequest, { rejectWithValue }) => {
    try {
      const response = await authService.register(userData)
      if (response.success && response.data) {
        return response.data
      } else {
        return rejectWithValue(response.message || '注册失败')
      }
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const logout = createAsyncThunk('auth/logout', async () => {
  await authService.logout()
})

export const refreshToken = createAsyncThunk<{ token: string; refresh_token: string }, void>(
  'auth/refreshToken',
  async (_, { rejectWithValue, getState }) => {
    try {
      const state = getState() as any
      const refreshToken = state.auth.refreshToken

      if (!refreshToken) {
        throw new Error('No refresh token available')
      }

      const response = await authService.refreshToken(refreshToken)
      if (response.success && response.data) {
        return response.data
      } else {
        return rejectWithValue(response.message || '刷新token失败')
      }
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setUser: (state, action: PayloadAction<User>) => {
      state.user = action.payload
      state.isAuthenticated = true
    },
    setToken: (state, action: PayloadAction<string>) => {
      state.token = action.payload
      localStorage.setItem('token', action.payload)
      state.isAuthenticated = true
    },
    clearAuth: (state) => {
      state.user = null
      state.token = null
      state.refreshToken = null
      state.isAuthenticated = false
      state.error = null
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      clearPipelineStorage()
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload
    },
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // Login
      .addCase(login.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(login.fulfilled, (state, action: PayloadAction<LoginResponse>) => {
        state.isLoading = false
        state.user = {
          id: action.payload.id,
          username: action.payload.username,
          email: action.payload.email,
          status: 1, // Active
          role: 0, // User
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
        state.token = action.payload.token
        state.refreshToken = action.payload.refresh_token
        state.isAuthenticated = true

        localStorage.setItem('token', action.payload.token)
        localStorage.setItem('refreshToken', action.payload.refresh_token)
      })
      .addCase(login.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '登录失败'
      })

      // Register
      .addCase(register.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(register.fulfilled, (state, action: PayloadAction<LoginResponse>) => {
        state.isLoading = false
        state.user = {
          id: action.payload.id,
          username: action.payload.username,
          email: action.payload.email,
          status: 1,
          role: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
        state.token = action.payload.token
        state.refreshToken = action.payload.refresh_token
        state.isAuthenticated = true

        localStorage.setItem('token', action.payload.token)
        localStorage.setItem('refreshToken', action.payload.refresh_token)
      })
      .addCase(register.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '注册失败'
      })

      // Logout
      .addCase(logout.fulfilled, (state) => {
        state.user = null
        state.token = null
        state.refreshToken = null
        state.isAuthenticated = false
        state.error = null

        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
        clearPipelineStorage()
      })

      // Refresh token
      .addCase(refreshToken.fulfilled, (state, action: PayloadAction<{ token: string; refresh_token: string }>) => {
        state.token = action.payload.token
        state.refreshToken = action.payload.refresh_token

        localStorage.setItem('token', action.payload.token)
        localStorage.setItem('refreshToken', action.payload.refresh_token)
      })
      .addCase(refreshToken.rejected, (state) => {
        state.user = null
        state.token = null
        state.refreshToken = null
        state.isAuthenticated = false

        localStorage.removeItem('token')
        localStorage.removeItem('refreshToken')
      })
  },
})

export const { setUser, setToken, clearAuth, setError, clearError } = authSlice.actions
export default authSlice.reducer