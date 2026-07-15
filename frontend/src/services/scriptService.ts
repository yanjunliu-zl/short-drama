import { api } from '@/api/axios'
import type {
  Script,
  ScriptGenerationRequest,
  ScriptUpdateRequest,
  ScriptResponse,
  GenerationStatus,
  ApiResponse,
  PaginatedResponse,
  ShotGenerationResponse,
  ShotVideoResultItem,
} from '@/types'
import type { ShotEpisode, ReferenceImages } from '@/types'

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
  getGenerationStatus: async (taskId: string): Promise<GenerationStatus> => {
    const response = await api.get<GenerationStatus>(`/v1/scripts/${taskId}/status`)
    return response.data as any
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

  // 从小说生成剧本
  generateScriptFromNovel: async (data: {
    title: string
    novel_content: string
    theme: string
    length: string
    characters?: string[]
    setting?: string
    style?: string
    user_id?: string
    excerpt_ratio?: number
  }): Promise<ScriptResponse> => {
    const response = await api.post<ScriptResponse>('/v1/scripts/generate/from-novel', data)
    return response.data
  },

  // 从剧本中提取主体（角色、地点、道具）
  extractEntities: async (content: string, scriptId?: number | string): Promise<{
    characters: { name: string; role: string; description: string }[]
    locations: { name: string; description: string }[]
    props: { name: string; description: string }[]
  }> => {
    const response = await api.post('/v1/scripts/extract-entities', { content, script_id: scriptId })
    return response.data
  },

  /** 上传完整剧本并自动分集 (JSON) */
  uploadAndSplitScript: async (data: {
    title: string
    content: string
  }): Promise<import('@/types').ScriptSplitResponse> => {
    const response = await api.post<import('@/types').ScriptSplitResponse>('/v1/scripts/split', data)
    return response.data
  },

  /** 上传剧本文件 — 服务端解析 + 自动分集 (multipart/form-data) */
  uploadScriptFile: async (
    file: File,
    title: string,
  ): Promise<import('@/types').ScriptSplitResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', title)
    const response = await api.post<import('@/types').ScriptSplitResponse>(
      '/v1/scripts/upload',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return response.data
  },

  /** 从大纲/想法同步生成剧本（直接等待结果，不走异步轮询） */
  generateScriptFromOutlineSync: async (data: {
    title: string
    outline: string
    theme: string
    length: string
    style?: string
    setting?: string
    user_id?: string
  }): Promise<import('@/types').ScriptSplitResponse> => {
    const response = await api.post<import('@/types').ScriptSplitResponse>('/v1/scripts/generate/from-outline-sync', data, { timeout: 600000 })
    return response.data
  },

  // 从大纲/想法生成剧本
  generateScriptFromOutline: async (data: {
    title: string
    outline: string
    theme: string
    length: string
    characters?: string[]
    setting?: string
    style?: string
    user_id?: string
  }): Promise<ScriptResponse> => {
    const response = await api.post<ScriptResponse>('/v1/scripts/generate/from-outline', data)
    return response.data
  },

  // ========== 智能分镜 (Shot-level) API ==========

  // 智能分镜 — 生成镜头级分镜
  generateShots: async (data: {
    title: string
    script: string
    episodeCount?: number
    episodeContents?: string[]
    style?: string
    sceneRefs?: string[]
    characterNames?: string[]
    user_id?: string
  }): Promise<ShotGenerationResponse> => {
    const response = await api.post<ShotGenerationResponse>('/v1/storyboard/shots/generate', data)
    return response.data
  },

  // 获取分镜生成状态
  getShotGenerationStatus: async (taskId: string): Promise<{
    task_id: string
    status: string
    progress: number
    error?: string
  }> => {
    const response = await api.get<{
      task_id: string
      status: string
      progress: number
      error?: string
    }>(`/v1/storyboard/shots/${taskId}/status`)
    return response.data
  },

  // 获取分镜生成结果
  getShotGenerationResult: async (taskId: string): Promise<ShotGenerationResponse> => {
    const response = await api.get<ShotGenerationResponse>(`/v1/storyboard/shots/${taskId}`)
    return response.data
  },

  // ========== 分镜视频生成 (Shot-to-Video) API ==========

  // 为每个分镜头批量生成视频
  generateShotsVideo: async (data: {
    storyboard_id?: string
    episodes: ShotEpisode[]
    referenceImages?: ReferenceImages
    style?: string
    width?: number
    height?: number
    fps?: number
    user_id?: string
  }): Promise<{
    task_id: string
    status: string
    message: string
    total_shots: number
    completed_shots: number
    results: ShotVideoResultItem[]
  }> => {
    const response = await api.post('/v1/llmhua/shots-to-video', data)
    return response.data
  },

  // 获取分镜视频生成状态（轮询用）
  getShotsVideoStatus: async (taskId: string): Promise<{
    task_id: string
    status: string
    progress: number
    result?: any
    error?: string
  }> => {
    const response = await api.get(`/v1/llmhua/shots-to-video/${taskId}/status`)
    return response.data
  },

  // 获取分镜视频生成结果
  getShotsVideoResult: async (taskId: string): Promise<{
    task_id: string
    status: string
    message: string
    total_shots: number
    completed_shots: number
    results: ShotVideoResultItem[]
  }> => {
    const response = await api.get(`/v1/llmhua/shots-to-video/${taskId}`)
    return response.data
  },

  // ========== 预览图像生成 API ==========

  // 为场景/角色/道具生成预览图像
  generatePreviewImage: async (data: {
    description: string
    category: 'scene' | 'character' | 'prop'
    style?: string
    width?: number
    height?: number
  }): Promise<{ task_id: string; status: string; image_url?: string; message: string }> => {
    const response = await api.post('/v1/llmhua/preview-image', data)
    return response.data
  },

  // 获取预览图像生成状态
  getPreviewImageStatus: async (taskId: string): Promise<{
    task_id: string
    status: string
    progress: number
    image_url?: string
    error?: string
  }> => {
    const response = await api.get(`/v1/llmhua/preview-image/${taskId}/status`)
    return response.data
  },
}