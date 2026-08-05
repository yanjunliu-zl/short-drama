import { api } from '@/api/axios'
import type { CommentListResponse, CommentItem, CommentCreateRequest } from '@/types/comment'

export const commentService = {
  /** 获取案例评论列表 */
  list: async (caseId: string, page = 1, pageSize = 20): Promise<CommentListResponse> => {
    const response = await api.get<CommentListResponse>(`/v1/comments/${caseId}`, {
      params: { page, pageSize },
    })
    return response.data
  },

  /** 发表评论 */
  create: async (caseId: string, data: CommentCreateRequest): Promise<CommentItem> => {
    const response = await api.post<CommentItem>(`/v1/comments/${caseId}`, data)
    return response.data
  },

  /** 删除评论 */
  delete: async (caseId: string, commentId: number): Promise<void> => {
    await api.delete(`/v1/comments/${caseId}/${commentId}`)
  },
}
