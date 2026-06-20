import { api } from '@/api/axios'

export interface WorkItem {
  id: string
  title: string
  status: string
  progress: number
  type: string
  description: string
  userId: string
  caseId: string
  createdDate: string
  lastModified: string
}

export interface WorkListResponse {
  works: WorkItem[]
  total: number
  page: number
  pages: number
}

export interface WorkListParams {
  userId?: string
  status?: string
  page?: number
  pageSize?: number
}

export const workService = {
  /** 获取作品列表 */
  getWorks: async (params: WorkListParams = {}): Promise<WorkListResponse> => {
    const response = await api.get<WorkListResponse>('/v1/works', { params })
    return response.data
  },

  /** 创建作品 */
  createWork: async (data: { title: string; type: string; description: string; userId: string }): Promise<WorkItem> => {
    const response = await api.post<WorkItem>('/v1/works', data)
    return response.data
  },
}
