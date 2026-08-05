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
  created_at: string
}

export interface FinalCutStatusResponse {
  task_id: string
  status: string
  progress: number
  video_url?: string
  thumbnail_url?: string
  error_message?: string
  updated_at: string
}

export interface FinalCutListResponse {
  tasks: FinalCutStatusResponse[]
  total: number
  page: number
  pages: number
}

export const finalCutService = {
  createFinalCut: async (data: FinalCutRequest): Promise<FinalCutResponse> => {
    const response = await api.post<FinalCutResponse>('/v1/final-cut', data)
    return response.data
  },

  getStatus: async (taskId: string): Promise<FinalCutStatusResponse> => {
    const response = await api.get<FinalCutStatusResponse>(`/v1/final-cut/${taskId}`)
    return response.data
  },

  listTasks: async (projectId: string, page = 1, pageSize = 10): Promise<FinalCutListResponse> => {
    const response = await api.get<FinalCutListResponse>('/v1/final-cut', {
      params: { project_id: projectId, page, pageSize },
    })
    return response.data
  },

  cancelTask: async (taskId: string): Promise<{ success: boolean }> => {
    const response = await api.delete('/v1/final-cut', { data: { task_id: taskId } })
    return response.data
  },
}
