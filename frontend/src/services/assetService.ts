import { api } from '@/api/axios'

export interface AssetItem {
  id: string
  name: string
  count: number
  type: string
  accessLevel?: string
  lastUpdate: string
}

export interface AssetListResponse {
  assets: AssetItem[]
  total: number
  page: number
  pages: number
}

export interface AssetListParams {
  user_id?: string
  page?: number
  pageSize?: number
}

export const assetService = {
  /** 获取个人资产 */
  getPersonalAssets: async (params: AssetListParams = {}): Promise<AssetListResponse> => {
    const response = await api.get<AssetListResponse>('/v1/assets/personal', { params })
    return response.data
  },

  /** 获取公司资产 */
  getCompanyAssets: async (params: AssetListParams = {}): Promise<AssetListResponse> => {
    const response = await api.get<AssetListResponse>('/v1/assets/company', { params })
    return response.data
  },
}
