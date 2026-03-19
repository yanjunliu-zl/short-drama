import { api } from '@/api/axios'
import type {
  Video,
  VideoGenerationRequest,
  VideoUpdateRequest,
  VideoResponse,
  VideoProcessingStatus,
  ApiResponse,
  PaginatedResponse,
} from '@/types'

export const videoService = {
  // 生成视频
  generateVideo: async (data: VideoGenerationRequest): Promise<ApiResponse<VideoResponse>> => {
    const response = await api.post<ApiResponse<VideoResponse>>('/v1/videos/generate', data)
    return response.data
  },

  // 获取视频列表
  getVideos: async (params: {
    page?: number
    pageSize?: number
    userId?: number
    status?: string
    keyword?: string
  }): Promise<ApiResponse<PaginatedResponse<Video>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<Video>>>('/v1/videos', { params })
    return response.data
  },

  // 获取单个视频
  getVideo: async (videoId: string): Promise<ApiResponse<Video>> => {
    const response = await api.get<ApiResponse<Video>>(`/v1/videos/${videoId}`)
    return response.data
  },

  // 更新视频信息
  updateVideo: async (videoId: string, data: VideoUpdateRequest): Promise<ApiResponse<Video>> => {
    const response = await api.put<ApiResponse<Video>>(`/v1/videos/${videoId}`, data)
    return response.data
  },

  // 删除视频
  deleteVideo: async (videoId: string): Promise<ApiResponse<void>> => {
    const response = await api.delete<ApiResponse<void>>(`/v1/videos/${videoId}`)
    return response.data
  },

  // 获取视频处理状态
  getProcessingStatus: async (taskId: string): Promise<ApiResponse<VideoProcessingStatus>> => {
    const response = await api.get<ApiResponse<VideoProcessingStatus>>(`/v1/videos/${taskId}/status`)
    return response.data
  },

  // 下载视频
  downloadVideo: async (videoId: string): Promise<Blob> => {
    const response = await api.get(`/v1/videos/${videoId}/download`, {
      responseType: 'blob',
    })
    return response.data
  },

  // 预览视频
  getVideoPreview: async (videoId: string): Promise<ApiResponse<{ preview_url: string }>> => {
    const response = await api.get<ApiResponse<{ preview_url: string }>>(`/v1/videos/${videoId}/preview`)
    return response.data
  },

  // 批量删除视频
  batchDeleteVideos: async (videoIds: string[]): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>('/v1/videos/batch-delete', { video_ids: videoIds })
    return response.data
  },

  // 获取视频统计
  getVideoStats: async (userId?: number): Promise<ApiResponse<{
    total_videos: number
    total_duration_seconds: number
    total_file_size_bytes: number
    videos_by_status: Record<string, number>
    videos_by_format: Record<string, number>
    videos_by_resolution: Record<string, number>
  }>> => {
    const response = await api.get<ApiResponse<any>>('/v1/videos/stats', { params: { user_id: userId } })
    return response.data
  },

  // 取消视频生成
  cancelVideoGeneration: async (taskId: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>(`/v1/videos/${taskId}/cancel`)
    return response.data
  },

  // 重新生成视频
  regenerateVideo: async (videoId: string): Promise<ApiResponse<VideoResponse>> => {
    const response = await api.post<ApiResponse<VideoResponse>>(`/v1/videos/${videoId}/regenerate`)
    return response.data
  },

  // 分享视频
  shareVideo: async (videoId: string, settings?: {
    expires_in?: number
    password?: string
    allow_download?: boolean
  }): Promise<ApiResponse<{ share_url: string; share_code: string }>> => {
    const response = await api.post<ApiResponse<{ share_url: string; share_code: string }>>(
      `/v1/videos/${videoId}/share`,
      settings
    )
    return response.data
  },

  // 获取分享的视频
  getSharedVideo: async (shareCode: string): Promise<ApiResponse<Video>> => {
    const response = await api.get<ApiResponse<Video>>(`/v1/videos/shared/${shareCode}`)
    return response.data
  },
}