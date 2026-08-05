import { api } from '@/api/axios'
import type { ApiResponse } from '@/types'

export interface PaymentOrder {
  id: string
  order_no: string
  transaction_id: string
  user_id: string
  amount: number
  currency: string
  method: 'wechat' | 'alipay'
  status: 'pending' | 'paid' | 'failed' | 'canceled' | 'refunded'
  subject: string
  description: string
  qr_code?: string
  pay_url?: string
  expire_time: string
  paid_at?: string
  created_at: string
}

export interface CreatePaymentParams {
  order_no: string
  user_id: string
  amount: number
  currency?: string
  method: 'wechat' | 'alipay'
  subject: string
  description?: string
  client_ip?: string
}

export interface RefundParams {
  refund_amount: number
  reason: string
}

export interface PaymentListResponse {
  payments: PaymentOrder[]
  total: number
  page: number
  pages: number
}

export const paymentService = {
  // 创建支付订单
  createPayment: async (data: CreatePaymentParams): Promise<ApiResponse<PaymentOrder>> => {
    const response = await api.post<ApiResponse<PaymentOrder>>('/v1/payments', data)
    return response.data
  },

  // 查询支付订单详情
  getPayment: async (paymentId: string): Promise<ApiResponse<PaymentOrder>> => {
    const response = await api.get<ApiResponse<PaymentOrder>>(`/v1/payments/${paymentId}`)
    return response.data
  },

  // 查询用户支付列表
  listPayments: async (params: {
    user_id: string
    page?: number
    pageSize?: number
    status?: string
  }): Promise<PaymentListResponse> => {
    const response = await api.get<PaymentListResponse>('/v1/payments', { params })
    return response.data
  },

  // 取消支付订单
  cancelPayment: async (paymentId: string): Promise<ApiResponse<{ success: boolean; message: string }>> => {
    const response = await api.post<ApiResponse<{ success: boolean; message: string }>>(`/v1/payments/${paymentId}/cancel`)
    return response.data
  },

  // 申请退款
  refundPayment: async (paymentId: string, data: RefundParams): Promise<ApiResponse<any>> => {
    const response = await api.post<ApiResponse<any>>(`/v1/payments/${paymentId}/refund`, data)
    return response.data
  },

  // 查询退款状态
  getRefundStatus: async (paymentId: string): Promise<ApiResponse<any>> => {
    const response = await api.get<ApiResponse<any>>(`/v1/payments/${paymentId}/refund`)
    return response.data
  },
}
