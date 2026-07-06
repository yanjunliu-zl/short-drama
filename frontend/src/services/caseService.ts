import { api } from '@/api/axios'
import type { CaseItem, CaseListResponse, CaseListParams } from '@/types/case'

export const caseService = {
  /** 获取案例广场列表 */
  getCases: async (params: CaseListParams = {}): Promise<CaseListResponse> => {
    const response = await api.get<CaseListResponse>('/v1/cases', { params })
    return response.data
  },

  /** 获取单个案例详情 */
  getCase: async (id: string): Promise<CaseItem> => {
    const response = await api.get<CaseItem>(`/v1/cases/${id}`)
    return response.data
  },

  /** 记录案例浏览 */
  recordView: async (id: string): Promise<void> => {
    await api.post(`/v1/cases/${id}/view`)
  },

  /** 点赞案例 */
  likeCase: async (id: string): Promise<{ likes: number }> => {
    const response = await api.post<{ likes: number }>(`/v1/cases/${id}/like`)
    return response.data
  },

  /** 分享案例 */
  recordShare: async (id: string): Promise<void> => {
    await api.post(`/v1/cases/${id}/share`)
  },

  /** ES 全文搜索 (smartcn分词 + 高亮 + 聚合) */
  search: async (params: { q?: string; tags?: string[]; genre?: string; page?: number; pageSize?: number }): Promise<any> => {
    const response = await api.get<any>('/v1/cases/search', { params })
    return response.data
  },

  /** 获取个性化推荐案例 (独立推荐微服务) */
  getRecommended: async (userId?: string, limit = 6): Promise<any> => {
    const response = await api.get<any>('/v1/recommendations/recommend', {
      params: { user_id: userId || undefined, limit },
    })
    // 适配新接口: { items, reason, total } → { cases, reason, total }
    return {
      cases: response.data.items || [],
      reason: response.data.reason || 'popular',
      total: response.data.total || 0,
    }
  },
}
