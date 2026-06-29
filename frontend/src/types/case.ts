// 案例广场 (Case Square) 类型定义

/** 单个案例 */
export interface CaseItem {
  id: string
  title: string
  description: string
  author: string
  likes: number
  views: number
  tags: string[]
  coverColor: string
  videoUrl?: string
  createdAt: string
  updatedAt: string
}

/** 案例列表响应 */
export interface CaseListResponse {
  cases: CaseItem[]
  total: number
  page: number
  pages: number
}

/** 案例列表请求参数 */
export interface CaseListParams {
  page?: number
  pageSize?: number
  tag?: string
  sortBy?: 'views' | 'likes' | 'createdAt'
  order?: 'asc' | 'desc'
}
