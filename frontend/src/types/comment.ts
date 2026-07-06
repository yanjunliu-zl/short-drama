/** 单条评论 */
export interface CommentItem {
  id: number
  case_id: string
  user_id: string
  author: string
  content: string
  created_at: string
}

/** 评论列表响应 */
export interface CommentListResponse {
  comments: CommentItem[]
  total: number
  page: number
  pages: number
}

/** 发表评论请求 */
export interface CommentCreateRequest {
  content: string
  author?: string
  user_id?: string
}
