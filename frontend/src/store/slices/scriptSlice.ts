import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import {
  Script,
  ScriptGenerationRequest,
  ScriptUpdateRequest,
  GenerationStatus,
} from '@/types'
import { scriptService } from '@/services/scriptService'

interface ScriptState {
  scripts: Script[]
  currentScript: Script | null
  scriptStats: any | null
  recommendedScripts: Script[]
  isLoading: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
  }
  generationStatus: GenerationStatus | null
  searchQuery: string
}

const initialState: ScriptState = {
  scripts: [],
  currentScript: null,
  scriptStats: null,
  recommendedScripts: [],
  isLoading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 10,
    total: 0,
  },
  generationStatus: null,
  searchQuery: '',
}

// Async thunks
export const generateScript = createAsyncThunk(
  'script/generateScript',
  async (data: ScriptGenerationRequest, { rejectWithValue }) => {
    try {
      const response = await scriptService.generateScript(data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchScripts = createAsyncThunk(
  'script/fetchScripts',
  async (params: { page?: number; pageSize?: number; userId?: number; status?: string; keyword?: string }, { rejectWithValue }) => {
    try {
      const response = await scriptService.getScripts(params)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchScript = createAsyncThunk(
  'script/fetchScript',
  async (scriptId: string, { rejectWithValue }) => {
    try {
      const response = await scriptService.getScript(scriptId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const updateScript = createAsyncThunk(
  'script/updateScript',
  async ({ scriptId, data }: { scriptId: string; data: ScriptUpdateRequest }, { rejectWithValue }) => {
    try {
      const response = await scriptService.updateScript(scriptId, data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const deleteScript = createAsyncThunk(
  'script/deleteScript',
  async (scriptId: string, { rejectWithValue }) => {
    try {
      await scriptService.deleteScript(scriptId)
      return scriptId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchGenerationStatus = createAsyncThunk(
  'script/fetchGenerationStatus',
  async (taskId: string, { rejectWithValue }) => {
    try {
      const response = await scriptService.getGenerationStatus(taskId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const batchDeleteScripts = createAsyncThunk(
  'script/batchDeleteScripts',
  async (scriptIds: string[], { rejectWithValue }) => {
    try {
      await scriptService.batchDeleteScripts(scriptIds)
      return scriptIds
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchScriptStats = createAsyncThunk(
  'script/fetchScriptStats',
  async (userId: number | undefined = undefined, { rejectWithValue }) => {
    try {
      const response = await scriptService.getScriptStats(userId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const searchScripts = createAsyncThunk(
  'script/searchScripts',
  async ({ query, params }: { query: string; params?: { page?: number; pageSize?: number } }, { rejectWithValue }) => {
    try {
      const response = await scriptService.searchScripts(query, params)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchRecommendedScripts = createAsyncThunk(
  'script/fetchRecommendedScripts',
  async (limit: number | undefined = undefined, { rejectWithValue }) => {
    try {
      const response = await scriptService.getRecommendedScripts(limit)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

const scriptSlice = createSlice({
  name: 'script',
  initialState,
  reducers: {
    setCurrentScript: (state, action: PayloadAction<Script | null>) => {
      state.currentScript = action.payload
    },
    setScripts: (state, action: PayloadAction<Script[]>) => {
      state.scripts = action.payload
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
    setSearchQuery: (state, action: PayloadAction<string>) => {
      state.searchQuery = action.payload
    },
    clearScriptState: (state) => {
      state.scripts = []
      state.currentScript = null
      state.scriptStats = null
      state.recommendedScripts = []
      state.error = null
      state.pagination = initialState.pagination
      state.generationStatus = null
      state.searchQuery = ''
    },
  },
  extraReducers: (builder) => {
    builder
      // generateScript
      .addCase(generateScript.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(generateScript.fulfilled, (state, _action) => {
        state.isLoading = false
        // Handle generation response (task ID)
        // The actual script will be fetched later via status
        // payload could be undefined, but we don't need it for this action
      })
      .addCase(generateScript.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '生成剧本失败'
      })
      // fetchScripts
      .addCase(fetchScripts.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchScripts.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.scripts = action.payload.items
          state.pagination = {
            page: action.payload.page,
            pageSize: action.payload.page_size,
            total: action.payload.total,
          }
        }
      })
      .addCase(fetchScripts.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取剧本列表失败'
      })
      // fetchScript
      .addCase(fetchScript.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchScript.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.currentScript = action.payload
        }
      })
      .addCase(fetchScript.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取剧本详情失败'
      })
      // updateScript
      .addCase(updateScript.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(updateScript.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.currentScript = payload
          // Update in scripts list if present
          const index = state.scripts.findIndex(s => s.id === payload.id)
          if (index !== -1) {
            state.scripts[index] = payload
          }
        }
      })
      .addCase(updateScript.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '更新剧本失败'
      })
      // deleteScript
      .addCase(deleteScript.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(deleteScript.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.scripts = state.scripts.filter(s => s.id !== payload)
          if (state.currentScript?.id === payload) {
            state.currentScript = null
          }
        }
      })
      .addCase(deleteScript.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '删除剧本失败'
      })
      // fetchGenerationStatus
      .addCase(fetchGenerationStatus.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchGenerationStatus.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.generationStatus = action.payload
        }
      })
      .addCase(fetchGenerationStatus.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取生成状态失败'
      })
      // batchDeleteScripts
      .addCase(batchDeleteScripts.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(batchDeleteScripts.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.scripts = state.scripts.filter(s => !payload.includes(s.id))
          if (state.currentScript && payload.includes(state.currentScript.id)) {
            state.currentScript = null
          }
        }
      })
      .addCase(batchDeleteScripts.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '批量删除剧本失败'
      })
      // fetchScriptStats
      .addCase(fetchScriptStats.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchScriptStats.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.scriptStats = payload
        }
      })
      .addCase(fetchScriptStats.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取剧本统计失败'
      })
      // searchScripts
      .addCase(searchScripts.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(searchScripts.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.scripts = action.payload.items
          state.pagination = {
            page: action.payload.page,
            pageSize: action.payload.page_size,
            total: action.payload.total,
          }
        }
      })
      .addCase(searchScripts.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '搜索剧本失败'
      })
      // fetchRecommendedScripts
      .addCase(fetchRecommendedScripts.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchRecommendedScripts.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.recommendedScripts = action.payload
        }
      })
      .addCase(fetchRecommendedScripts.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取推荐剧本失败'
      })
  },
})

export const {
  setCurrentScript,
  setScripts,
  setError,
  clearError,
  setPagination,
  setSearchQuery,
  clearScriptState,
} = scriptSlice.actions

export default scriptSlice.reducer