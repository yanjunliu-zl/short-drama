import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { User, UserProfile, UpdateUserRequest, UpdateUserProfileRequest, PaginatedResponse } from '@/types'
import { userService } from '@/services/userService'

interface UserState {
  currentUser: User | null
  userProfile: UserProfile | null
  users: User[]
  isLoading: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
  }
}

const initialState: UserState = {
  currentUser: null,
  userProfile: null,
  users: [],
  isLoading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 10,
    total: 0,
  },
}

// Async thunks
export const fetchCurrentUser = createAsyncThunk(
  'user/fetchCurrentUser',
  async (_, { rejectWithValue }) => {
    try {
      const response = await userService.getCurrentUser()
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchUserProfile = createAsyncThunk(
  'user/fetchUserProfile',
  async (userId: number, { rejectWithValue }) => {
    try {
      const response = await userService.getUserProfile(userId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const updateUser = createAsyncThunk(
  'user/updateUser',
  async ({ userId, data }: { userId: number; data: UpdateUserRequest }, { rejectWithValue }) => {
    try {
      const response = await userService.updateUser(userId, data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const updateUserProfile = createAsyncThunk(
  'user/updateUserProfile',
  async ({ userId, data }: { userId: number; data: UpdateUserProfileRequest }, { rejectWithValue }) => {
    try {
      const response = await userService.updateUserProfile(userId, data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchUsers = createAsyncThunk(
  'user/fetchUsers',
  async (params: { page?: number; pageSize?: number; keyword?: string }, { rejectWithValue }) => {
    try {
      const response = await userService.getUsers(params)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    setCurrentUser: (state, action: PayloadAction<User>) => {
      state.currentUser = action.payload
    },
    clearCurrentUser: (state) => {
      state.currentUser = null
      state.userProfile = null
    },
    setUsers: (state, action: PayloadAction<User[]>) => {
      state.users = action.payload
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload
    },
    clearError: (state) => {
      state.error = null
    },
    setPagination: (state, action: PayloadAction<{ page: number; pageSize: number; total: number }>) => {
      state.pagination = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch current user
      .addCase(fetchCurrentUser.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action: PayloadAction<User | undefined>) => {
        state.isLoading = false
        state.currentUser = action.payload || null
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取用户信息失败'
      })

      // Fetch user profile
      .addCase(fetchUserProfile.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchUserProfile.fulfilled, (state, action: PayloadAction<UserProfile | undefined>) => {
        state.isLoading = false
        state.userProfile = action.payload || null
      })
      .addCase(fetchUserProfile.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取用户资料失败'
      })

      // Update user
      .addCase(updateUser.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(updateUser.fulfilled, (state, action: PayloadAction<User | undefined>) => {
        state.isLoading = false
        state.currentUser = action.payload || null
      })
      .addCase(updateUser.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '更新用户信息失败'
      })

      // Update user profile
      .addCase(updateUserProfile.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(updateUserProfile.fulfilled, (state, action: PayloadAction<UserProfile | undefined>) => {
        state.isLoading = false
        state.userProfile = action.payload || null
      })
      .addCase(updateUserProfile.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '更新用户资料失败'
      })

      // Fetch users
      .addCase(fetchUsers.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchUsers.fulfilled, (state, action: PayloadAction<PaginatedResponse<User> | undefined>) => {
        state.isLoading = false
        if (action.payload) {
          state.users = action.payload.items
          state.pagination = {
            page: action.payload.page,
            pageSize: action.payload.page_size,
            total: action.payload.total,
          }
        } else {
          state.users = []
          state.pagination = {
            page: 1,
            pageSize: 10,
            total: 0,
          }
        }
      })
      .addCase(fetchUsers.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取用户列表失败'
      })
  },
})

export const {
  setCurrentUser,
  clearCurrentUser,
  setUsers,
  setError,
  clearError,
  setPagination,
} = userSlice.actions

export default userSlice.reducer