import { api } from '@/api/axios'
import type {
  Order,
  CreateOrderRequest,
  PaymentRequest,
  OrderResponse,
  PaymentResponse,
  Subscription,
  SubscriptionPlan,
  ApiResponse,
  PaginatedResponse,
} from '@/types'

export const orderService = {
  // 创建订单
  createOrder: async (data: CreateOrderRequest): Promise<ApiResponse<OrderResponse>> => {
    const response = await api.post<ApiResponse<OrderResponse>>('/v1/orders', data)
    return response.data
  },

  // 获取订单列表
  getOrders: async (params: {
    page?: number
    pageSize?: number
    userId?: number
    status?: string
    type?: string
  }): Promise<ApiResponse<PaginatedResponse<Order>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<Order>>>('/v1/orders', { params })
    return response.data
  },

  // 获取单个订单
  getOrder: async (orderId: string): Promise<ApiResponse<OrderResponse>> => {
    const response = await api.get<ApiResponse<OrderResponse>>(`/v1/orders/${orderId}`)
    return response.data
  },

  // 取消订单
  cancelOrder: async (orderId: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>(`/v1/orders/${orderId}/cancel`)
    return response.data
  },

  // 创建支付
  createPayment: async (data: PaymentRequest): Promise<ApiResponse<PaymentResponse>> => {
    const response = await api.post<ApiResponse<PaymentResponse>>('/v1/orders/payment', data)
    return response.data
  },

  // 查询支付状态
  getPaymentStatus: async (paymentId: string): Promise<ApiResponse<PaymentResponse>> => {
    const response = await api.get<ApiResponse<PaymentResponse>>(`/v1/orders/payment/${paymentId}`)
    return response.data
  },

  // 退款
  refundOrder: async (orderId: string, reason?: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>(`/v1/orders/${orderId}/refund`, { reason })
    return response.data
  },

  // 获取订阅计划
  getSubscriptionPlans: async (): Promise<ApiResponse<SubscriptionPlan[]>> => {
    const response = await api.get<ApiResponse<SubscriptionPlan[]>>('/v1/orders/subscription/plans')
    return response.data
  },

  // 获取用户订阅
  getUserSubscription: async (userId: number): Promise<ApiResponse<Subscription>> => {
    const response = await api.get<ApiResponse<Subscription>>(`/v1/orders/subscription/user/${userId}`)
    return response.data
  },

  // 创建订阅
  createSubscription: async (planId: string, paymentMethod: string): Promise<ApiResponse<Subscription>> => {
    const response = await api.post<ApiResponse<Subscription>>('/v1/orders/subscription', {
      plan_id: planId,
      payment_method: paymentMethod,
    })
    return response.data
  },

  // 取消订阅
  cancelSubscription: async (subscriptionId: string): Promise<ApiResponse<void>> => {
    const response = await api.post<ApiResponse<void>>(`/v1/orders/subscription/${subscriptionId}/cancel`)
    return response.data
  },

  // 更新订阅
  updateSubscription: async (subscriptionId: string, planId: string): Promise<ApiResponse<Subscription>> => {
    const response = await api.put<ApiResponse<Subscription>>(`/v1/orders/subscription/${subscriptionId}`, {
      plan_id: planId,
    })
    return response.data
  },

  // 获取订单统计
  getOrderStats: async (userId?: number): Promise<ApiResponse<{
    total_orders: number
    total_amount: number
    successful_orders: number
    pending_orders: number
    orders_by_type: Record<string, number>
    orders_by_status: Record<string, number>
    monthly_revenue: Array<{ month: string; revenue: number }>
  }>> => {
    const response = await api.get<ApiResponse<any>>('/v1/orders/stats', { params: { user_id: userId } })
    return response.data
  },

  // 获取发票信息
  getInvoice: async (orderId: string): Promise<Blob> => {
    const response = await api.get(`/v1/orders/${orderId}/invoice`, {
      responseType: 'blob',
    })
    return response.data
  },

  // 获取消费记录
  getConsumptionRecords: async (params: {
    page?: number
    pageSize?: number
    userId?: number
    startDate?: string
    endDate?: string
  }): Promise<ApiResponse<PaginatedResponse<any>>> => {
    const response = await api.get<ApiResponse<PaginatedResponse<any>>>('/v1/orders/consumption', { params })
    return response.data
  },
}