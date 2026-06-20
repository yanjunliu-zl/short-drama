import { api } from '@/api/axios'

export interface FinalCutRequest {
  project_id: string
  episode_title?: string
  video_urls: string[]
  output_format?: string
}

export interface FinalCutResponse {
  task_id: string
  status: string
  video_url?: string
  thumbnail_url?: string
  duration?: number
  progress?: number
  error_message?: string
  updated_at?: string
  created_at?: string
}

export const finalCutService = {
  // 创建最终剪辑任务（拼接所有镜头视频）
  createFinalCut: async (data: FinalCutRequest): Promise<FinalCutResponse> => {
    const response = await api.post<FinalCutResponse>('/v1/final-cut', data)
    return response.data
  },

  // 获取剪辑任务状态（轮询用）
  getFinalCutStatus: async (taskId: string): Promise<FinalCutResponse> => {
    const response = await api.get<FinalCutResponse>(`/v1/final-cut/${taskId}`)
    return response.data
  },

  // 获取剪辑任务列表
  getFinalCutList: async (params: {
    project_id: string
    page?: number
    pageSize?: number
  }): Promise<{
    tasks: FinalCutResponse[]
    total: number
    page: number
    pages: number
  }> => {
    const response = await api.get('/v1/final-cut', { params })
    return response.data
  },
}
