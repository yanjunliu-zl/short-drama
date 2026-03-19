import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import {
  Video,
  VideoGenerationRequest,
  VideoUpdateRequest,
  VideoProcessingStatus,
} from '@/types'
import { videoService } from '@/services/videoService'

interface VideoState {
  videos: Video[]
  currentVideo: Video | null
  videoStats: any | null
  isLoading: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
  }
  processingStatus: VideoProcessingStatus | null
  searchQuery: string
  sharedVideo: Video | null
}

const initialState: VideoState = {
  videos: [],
  currentVideo: null,
  videoStats: null,
  isLoading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 10,
    total: 0,
  },
  processingStatus: null,
  searchQuery: '',
  sharedVideo: null,
}

// Async thunks
export const generateVideo = createAsyncThunk(
  'video/generateVideo',
  async (data: VideoGenerationRequest, { rejectWithValue }) => {
    try {
      const response = await videoService.generateVideo(data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchVideos = createAsyncThunk(
  'video/fetchVideos',
  async (params: { page?: number; pageSize?: number; userId?: number; status?: string; keyword?: string }, { rejectWithValue }) => {
    try {
      const response = await videoService.getVideos(params)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchVideo = createAsyncThunk(
  'video/fetchVideo',
  async (videoId: string, { rejectWithValue }) => {
    try {
      const response = await videoService.getVideo(videoId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const updateVideo = createAsyncThunk(
  'video/updateVideo',
  async ({ videoId, data }: { videoId: string; data: VideoUpdateRequest }, { rejectWithValue }) => {
    try {
      const response = await videoService.updateVideo(videoId, data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const deleteVideo = createAsyncThunk(
  'video/deleteVideo',
  async (videoId: string, { rejectWithValue }) => {
    try {
      await videoService.deleteVideo(videoId)
      return videoId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchProcessingStatus = createAsyncThunk(
  'video/fetchProcessingStatus',
  async (taskId: string, { rejectWithValue }) => {
    try {
      const response = await videoService.getProcessingStatus(taskId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const batchDeleteVideos = createAsyncThunk(
  'video/batchDeleteVideos',
  async (videoIds: string[], { rejectWithValue }) => {
    try {
      await videoService.batchDeleteVideos(videoIds)
      return videoIds
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchVideoStats = createAsyncThunk(
  'video/fetchVideoStats',
  async (userId: number | undefined = undefined, { rejectWithValue }) => {
    try {
      const response = await videoService.getVideoStats(userId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const cancelVideoGeneration = createAsyncThunk(
  'video/cancelVideoGeneration',
  async (taskId: string, { rejectWithValue }) => {
    try {
      await videoService.cancelVideoGeneration(taskId)
      return taskId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const regenerateVideo = createAsyncThunk(
  'video/regenerateVideo',
  async (videoId: string, { rejectWithValue }) => {
    try {
      const response = await videoService.regenerateVideo(videoId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const shareVideo = createAsyncThunk(
  'video/shareVideo',
  async ({ videoId, settings }: { videoId: string; settings?: any }, { rejectWithValue }) => {
    try {
      const response = await videoService.shareVideo(videoId, settings)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchSharedVideo = createAsyncThunk(
  'video/fetchSharedVideo',
  async (shareCode: string, { rejectWithValue }) => {
    try {
      const response = await videoService.getSharedVideo(shareCode)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

const videoSlice = createSlice({
  name: 'video',
  initialState,
  reducers: {
    setCurrentVideo: (state, action: PayloadAction<Video | null>) => {
      state.currentVideo = action.payload
    },
    setVideos: (state, action: PayloadAction<Video[]>) => {
      state.videos = action.payload
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
    setSharedVideo: (state, action: PayloadAction<Video | null>) => {
      state.sharedVideo = action.payload
    },
    clearVideoState: (state) => {
      state.videos = []
      state.currentVideo = null
      state.videoStats = null
      state.error = null
      state.pagination = initialState.pagination
      state.processingStatus = null
      state.searchQuery = ''
      state.sharedVideo = null
    },
  },
  extraReducers: (builder) => {
    builder
      // generateVideo
      .addCase(generateVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(generateVideo.fulfilled, (state, _action) => {
        state.isLoading = false
        // Handle generation response (task ID)
        // payload could be undefined, but we don't need it for this action
      })
      .addCase(generateVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '生成视频失败'
      })
      // fetchVideos
      .addCase(fetchVideos.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchVideos.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.videos = action.payload.items
          state.pagination = {
            page: action.payload.page,
            pageSize: action.payload.page_size,
            total: action.payload.total,
          }
        }
      })
      .addCase(fetchVideos.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取视频列表失败'
      })
      // fetchVideo
      .addCase(fetchVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchVideo.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.currentVideo = action.payload
        }
      })
      .addCase(fetchVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取视频详情失败'
      })
      // updateVideo
      .addCase(updateVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(updateVideo.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.currentVideo = payload
          const index = state.videos.findIndex(v => v.id === payload.id)
          if (index !== -1) {
            state.videos[index] = payload
          }
        }
      })
      .addCase(updateVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '更新视频失败'
      })
      // deleteVideo
      .addCase(deleteVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(deleteVideo.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.videos = state.videos.filter(v => v.id !== payload)
          if (state.currentVideo?.id === payload) {
            state.currentVideo = null
          }
        }
      })
      .addCase(deleteVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '删除视频失败'
      })
      // fetchProcessingStatus
      .addCase(fetchProcessingStatus.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchProcessingStatus.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.processingStatus = action.payload
        }
      })
      .addCase(fetchProcessingStatus.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取处理状态失败'
      })
      // batchDeleteVideos
      .addCase(batchDeleteVideos.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(batchDeleteVideos.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.videos = state.videos.filter(v => !payload.includes(v.id))
          if (state.currentVideo && payload.includes(state.currentVideo.id)) {
            state.currentVideo = null
          }
        }
      })
      .addCase(batchDeleteVideos.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '批量删除视频失败'
      })
      // fetchVideoStats
      .addCase(fetchVideoStats.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchVideoStats.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.videoStats = payload
        }
      })
      .addCase(fetchVideoStats.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取视频统计失败'
      })
      // cancelVideoGeneration
      .addCase(cancelVideoGeneration.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(cancelVideoGeneration.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          // Update processing status if needed
          if (state.processingStatus?.task_id === payload) {
            state.processingStatus.status = 'failed'
          }
        }
      })
      .addCase(cancelVideoGeneration.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '取消视频生成失败'
      })
      // regenerateVideo
      .addCase(regenerateVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(regenerateVideo.fulfilled, (state, _action) => {
        state.isLoading = false
        // Handle regeneration response
        // payload could be undefined, but we don't need it for this action
      })
      .addCase(regenerateVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '重新生成视频失败'
      })
      // shareVideo
      .addCase(shareVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(shareVideo.fulfilled, (state, _action) => {
        state.isLoading = false
        // Share successful, maybe store share info
        // payload could be undefined, but we don't need it for this action
      })
      .addCase(shareVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '分享视频失败'
      })
      // fetchSharedVideo
      .addCase(fetchSharedVideo.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchSharedVideo.fulfilled, (state, action) => {
        state.isLoading = false
        if (action.payload) {
          state.sharedVideo = action.payload
        }
      })
      .addCase(fetchSharedVideo.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取分享视频失败'
      })
  },
})

export const {
  setCurrentVideo,
  setVideos,
  setError,
  clearError,
  setPagination,
  setSearchQuery,
  setSharedVideo,
  clearVideoState,
} = videoSlice.actions

export default videoSlice.reducer