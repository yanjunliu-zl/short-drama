import { api } from '@/api/axios'

export interface PipelineState {
  script?: any
  scenes?: any[]
  characters?: any[]
  props?: any[]
  storyboard?: any
  videoResults?: any
  finalCut?: any
  workId?: string
  updatedAt?: string
}

export interface SavePipelineStateResponse {
  workId: string
  data: PipelineState
}

export interface GetPipelineStateResponse {
  workId: string
  data: PipelineState | null
}

export const pipelineService = {
  /** 保存完整管道状态到后端 */
  savePipelineState: async (workId: string, data: PipelineState): Promise<SavePipelineStateResponse> => {
    const response = await api.put<SavePipelineStateResponse>(`/v1/works/${workId}/pipeline-state`, { data })
    return response.data
  },

  /** 从后端加载完整管道状态 */
  getPipelineState: async (workId: string): Promise<GetPipelineStateResponse> => {
    const response = await api.get<GetPipelineStateResponse>(`/v1/works/${workId}/pipeline-state`)
    return response.data
  },
}
