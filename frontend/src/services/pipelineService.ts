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

export type PipelineStep =
  | 'script'
  | 'scenes'
  | 'characters'
  | 'props'
  | 'storyboard'
  | 'referenceImages'
  | 'videoResults'
  | 'finalCut'

export interface SavePipelineStateResponse {
  workId: string
  data: PipelineState
}

export interface GetPipelineStateResponse {
  workId: string
  data: PipelineState | null
}

export interface PipelineStepResponse {
  workId: string
  step: string
  data: any
}

export const VALID_STEPS: PipelineStep[] = [
  'script', 'scenes', 'characters', 'props',
  'storyboard', 'referenceImages', 'videoResults', 'finalCut',
]

function isValidStep(step: string): step is PipelineStep {
  return VALID_STEPS.includes(step as PipelineStep)
}

export const pipelineService = {
  // ── 全量读写（保留兼容） ──

  /** 保存完整管道状态到后端 */
  savePipelineState: async (workId: string, data: PipelineState): Promise<SavePipelineStateResponse> => {
    const response = await api.put<SavePipelineStateResponse>(`/v1/works/${workId}/pipeline`, { data })
    return response.data
  },

  /** 从后端加载完整管道状态 */
  getPipelineState: async (workId: string): Promise<GetPipelineStateResponse> => {
    const response = await api.get<GetPipelineStateResponse>(`/v1/works/${workId}/pipeline`)
    return response.data
  },

  // ── 单步读写（推荐！原子写入，无竞态） ──

  /**
   * 原子写入单个 pipeline step 到后端 Redis hash。
   * 不会读取/合并其他 step，不会产生竞态覆盖。
   */
  savePipelineStep: async (workId: string, step: PipelineStep, data: any): Promise<PipelineStepResponse> => {
    if (!isValidStep(step)) {
      throw new Error(`Invalid pipeline step: ${step}`)
    }
    const response = await api.put<PipelineStepResponse>(`/v1/works/${workId}/pipeline/${step}`, { data })
    return response.data
  },

  /**
   * 读取单个 pipeline step。
   * Redis hash 优先命中，miss 时自动从 MySQL 恢复。
   */
  getPipelineStep: async (workId: string, step: PipelineStep): Promise<PipelineStepResponse> => {
    if (!isValidStep(step)) {
      throw new Error(`Invalid pipeline step: ${step}`)
    }
    const response = await api.get<PipelineStepResponse>(`/v1/works/${workId}/pipeline/${step}`)
    return response.data
  },
}
