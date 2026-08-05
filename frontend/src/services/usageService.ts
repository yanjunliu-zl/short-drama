import { api } from '@/api/axios'

export interface UsageSummary {
  userId: string
  period: string
  llmCalls: number
  llmTokens: number
  llmCost: number
  imageCalls: number
  imageCost: number
  videoCalls: number
  videoCost: number
  totalCost: number
}

export interface UsageRecordItem {
  id: number
  userId: string
  modelType: string
  modelName: string
  tokensIn: number
  tokensOut: number
  callCount: number
  durationMs: number
  endpoint: string
  serviceName: string
  costEstimate: number
  createdAt: string
}

export const usageService = {
  getSummary: async (userId: string, period: string = 'month'): Promise<UsageSummary> => {
    const response = await api.get('/v1/usage/summary', { params: { userId, period } })
    return response.data
  },

  getHistory: async (userId: string): Promise<{ records: UsageRecordItem[] }> => {
    const response = await api.get('/v1/usage/history', { params: { userId } })
    return response.data
  },
}
