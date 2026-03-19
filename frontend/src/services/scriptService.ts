import { api } from '@/api/axios'
import type {
  Script,
  ScriptGenerationRequest,
  ScriptUpdateRequest,
  ScriptResponse,
  GenerationStatus,
  ApiResponse,
  PaginatedResponse,
} from '@/types'

export const scriptService = {
  // 生成剧本
  generateScript: async (data: ScriptGenerationRequest): Promise<ApiResponse<ScriptResponse>> => {
    const response = await api.post<ApiResponse<ScriptResponse>>('/v1/scripts/generate', data)
    return response.data
  },

  // 获取剧本列表
  getScripts: async (params: {
    page?: number
    pageSize?: number
    userId?: number
    status?: string
    keyword?: string
  }): Promise<ApiResponse<PaginatedResponse<Script>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<Script>>>('/v1/scripts', { params })
    return response.data
  },

  // 获取单个剧本
  getScript: async (scriptId: string): Promise<ApiResponse<Script>> => {
    const response = await api.get<ApiResponse<Script>>(`/v1/scripts/${scriptId}`)
    return response.data
  },

  // 更新剧本
  updateScript: async (scriptId: string, data: ScriptUpdateRequest): Promise<ApiResponse<Script>> => {
    const response = await api.put<ApiResponse<Script>>(`/v1/scripts/${scriptId}`, data)
    return response.data
  },

  // 删除剧本
  deleteScript: async (scriptId: string): Promise<ApiResponse<void>> => {
    const response = await api.delete<ApiResponse<void>>(`/v1/scripts/${scriptId}`)
    return response.data
  },

  // 获取生成状态
  getGenerationStatus: async (taskId: string): Promise<ApiResponse<GenerationStatus>> => {
    const response = await api.get<ApiResponse<GenerationStatus>>(`/v1/scripts/${taskId}/status`)
    return response.data
  },

  // 批量删除剧本
  batchDeleteScripts: async (scriptIds: string[]): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>('/v1/scripts/batch-delete', { script_ids: scriptIds })
    return response.data
  },

  // 导出剧本
  exportScript: async (scriptId: string, format: 'pdf' | 'docx' | 'txt'): Promise<Blob> => {
    const response = await api.get(`/v1/scripts/${scriptId}/export`, {
      params: { format },
      responseType: 'blob',
    })
    return response.data
  },

  // 复制剧本
  duplicateScript: async (scriptId: string): Promise<ApiResponse<Script>> => {
    const response = await api.post<ApiResponse<Script>>(`/v1/scripts/${scriptId}/duplicate`)
    return response.data
  },

  // 获取剧本统计
  getScriptStats: async (userId?: number): Promise<ApiResponse<{
    total_scripts: number
    total_characters: number
    total_scenes: number
    scripts_by_genre: Record<string, number>
    scripts_by_status: Record<string, number>
  }>> => {
    const response = await api.get<ApiResponse<any>>('/v1/scripts/stats', { params: { user_id: userId } })
    return response.data
  },

  // 搜索剧本
  searchScripts: async (query: string, params?: {
    page?: number
    pageSize?: number
  }): Promise<ApiResponse<PaginatedResponse<Script>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<Script>>>('/v1/scripts/search', {
      params: { q: query, ...params },
    })
    return response.data
  },

  // 获取推荐剧本
  getRecommendedScripts: async (limit?: number): Promise<ApiResponse<Script[]>> => {
    const response = await api.get<ApiResponse<Script[]>>('/v1/scripts/recommended', {
      params: { limit: limit || 10 },
    })
    return response.data
  },
}