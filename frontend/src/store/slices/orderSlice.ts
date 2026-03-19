import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { OrderStatus, SubscriptionStatus } from '@/types'
import type {
  Order,
  CreateOrderRequest,
  PaymentRequest,
  OrderResponse,
  PaymentResponse,
  Subscription,
  SubscriptionPlan,
} from '@/types'
import { orderService } from '@/services/orderService'

interface OrderState {
  orders: Order[]
  currentOrder: OrderResponse | null
  subscriptionPlans: SubscriptionPlan[]
  userSubscription: Subscription | null
  paymentStatus: PaymentResponse | null
  orderStats: any | null
  isLoading: boolean
  error: string | null
  pagination: {
    page: number
    pageSize: number
    total: number
  }
}

const initialState: OrderState = {
  orders: [],
  currentOrder: null,
  subscriptionPlans: [],
  userSubscription: null,
  paymentStatus: null,
  orderStats: null,
  isLoading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 10,
    total: 0,
  },
}

// Async thunks
export const createOrder = createAsyncThunk(
  'order/createOrder',
  async (data: CreateOrderRequest, { rejectWithValue }) => {
    try {
      const response = await orderService.createOrder(data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchOrders = createAsyncThunk(
  'order/fetchOrders',
  async (params: { page?: number; pageSize?: number; userId?: number; status?: string; type?: string }, { rejectWithValue }) => {
    try {
      const response = await orderService.getOrders(params)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchOrder = createAsyncThunk(
  'order/fetchOrder',
  async (orderId: string, { rejectWithValue }) => {
    try {
      const response = await orderService.getOrder(orderId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const cancelOrder = createAsyncThunk(
  'order/cancelOrder',
  async (orderId: string, { rejectWithValue }) => {
    try {
      await orderService.cancelOrder(orderId)
      return orderId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const createPayment = createAsyncThunk(
  'order/createPayment',
  async (data: PaymentRequest, { rejectWithValue }) => {
    try {
      const response = await orderService.createPayment(data)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchPaymentStatus = createAsyncThunk(
  'order/fetchPaymentStatus',
  async (paymentId: string, { rejectWithValue }) => {
    try {
      const response = await orderService.getPaymentStatus(paymentId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const refundOrder = createAsyncThunk(
  'order/refundOrder',
  async ({ orderId, reason }: { orderId: string; reason?: string }, { rejectWithValue }) => {
    try {
      await orderService.refundOrder(orderId, reason)
      return orderId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchSubscriptionPlans = createAsyncThunk(
  'order/fetchSubscriptionPlans',
  async (_, { rejectWithValue }) => {
    try {
      const response = await orderService.getSubscriptionPlans()
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchUserSubscription = createAsyncThunk(
  'order/fetchUserSubscription',
  async (userId: number, { rejectWithValue }) => {
    try {
      const response = await orderService.getUserSubscription(userId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const createSubscription = createAsyncThunk(
  'order/createSubscription',
  async ({ planId, paymentMethod }: { planId: string; paymentMethod: string }, { rejectWithValue }) => {
    try {
      const response = await orderService.createSubscription(planId, paymentMethod)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const cancelSubscription = createAsyncThunk(
  'order/cancelSubscription',
  async (subscriptionId: string, { rejectWithValue }) => {
    try {
      await orderService.cancelSubscription(subscriptionId)
      return subscriptionId
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const updateSubscription = createAsyncThunk(
  'order/updateSubscription',
  async ({ subscriptionId, planId }: { subscriptionId: string; planId: string }, { rejectWithValue }) => {
    try {
      const response = await orderService.updateSubscription(subscriptionId, planId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

export const fetchOrderStats = createAsyncThunk(
  'order/fetchOrderStats',
  async (userId: number | undefined = undefined, { rejectWithValue }) => {
    try {
      const response = await orderService.getOrderStats(userId)
      return response.data
    } catch (error: any) {
      return rejectWithValue(error.response?.data || error.message)
    }
  }
)

const orderSlice = createSlice({
  name: 'order',
  initialState,
  reducers: {
    setCurrentOrder: (state, action: PayloadAction<OrderResponse | null>) => {
      state.currentOrder = action.payload
    },
    setOrders: (state, action: PayloadAction<Order[]>) => {
      state.orders = action.payload
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload
    },
    clearError: (state) => {
      state.error = null
    },
    setPagination: (state, action: PayloadAction<{ page: number; pageSize: number; total: number }>) => {
      state.pagination = action.payload
    },
    setSubscriptionPlans: (state, action: PayloadAction<SubscriptionPlan[]>) => {
      state.subscriptionPlans = action.payload
    },
    setUserSubscription: (state, action: PayloadAction<Subscription | null>) => {
      state.userSubscription = action.payload
    },
    setPaymentStatus: (state, action: PayloadAction<PaymentResponse | null>) => {
      state.paymentStatus = action.payload
    },
    clearOrderState: (state) => {
      state.orders = []
      state.currentOrder = null
      state.subscriptionPlans = []
      state.userSubscription = null
      state.paymentStatus = null
      state.orderStats = null
      state.error = null
      state.pagination = initialState.pagination
    },
  },
  extraReducers: (builder) => {
    builder
      // createOrder
      .addCase(createOrder.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(createOrder.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.currentOrder = payload
          // Add to orders list
          state.orders = [payload.order, ...state.orders]
        }
      })
      .addCase(createOrder.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '创建订单失败'
      })
      // fetchOrders
      .addCase(fetchOrders.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.orders = payload.items
          state.pagination = {
            page: payload.page,
            pageSize: payload.page_size,
            total: payload.total,
          }
        }
      })
      .addCase(fetchOrders.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取订单列表失败'
      })
      // fetchOrder
      .addCase(fetchOrder.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchOrder.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          state.currentOrder = payload
        }
      })
      .addCase(fetchOrder.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取订单详情失败'
      })
      // cancelOrder
      .addCase(cancelOrder.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(cancelOrder.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          const index = state.orders.findIndex(o => o.id === payload)
          if (index !== -1) {
            state.orders[index].status = OrderStatus.Cancelled
          }
          if (state.currentOrder?.order.id === payload) {
            state.currentOrder.order.status = OrderStatus.Cancelled
          }
        }
      })
      .addCase(cancelOrder.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '取消订单失败'
      })
      // createPayment
      .addCase(createPayment.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(createPayment.fulfilled, (state, action: PayloadAction<PaymentResponse | undefined>) => {
        state.isLoading = false
        state.paymentStatus = action.payload || null
        // Update order payment status
        if (action.payload && state.currentOrder?.order.id === action.payload.order_id) {
          state.currentOrder.payment = action.payload
        }
      })
      .addCase(createPayment.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '创建支付失败'
      })
      // fetchPaymentStatus
      .addCase(fetchPaymentStatus.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchPaymentStatus.fulfilled, (state, action: PayloadAction<PaymentResponse | undefined>) => {
        state.isLoading = false
        state.paymentStatus = action.payload || null
      })
      .addCase(fetchPaymentStatus.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取支付状态失败'
      })
      // refundOrder
      .addCase(refundOrder.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(refundOrder.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload) {
          const index = state.orders.findIndex(o => o.id === payload)
          if (index !== -1) {
            state.orders[index].status = OrderStatus.Refunded
          }
          if (state.currentOrder?.order.id === payload) {
            state.currentOrder.order.status = OrderStatus.Refunded
          }
        }
      })
      .addCase(refundOrder.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '退款失败'
      })
      // fetchSubscriptionPlans
      .addCase(fetchSubscriptionPlans.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchSubscriptionPlans.fulfilled, (state, action: PayloadAction<SubscriptionPlan[] | undefined>) => {
        state.isLoading = false
        state.subscriptionPlans = action.payload || []
      })
      .addCase(fetchSubscriptionPlans.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取订阅计划失败'
      })
      // fetchUserSubscription
      .addCase(fetchUserSubscription.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchUserSubscription.fulfilled, (state, action: PayloadAction<Subscription | undefined>) => {
        state.isLoading = false
        state.userSubscription = action.payload || null
      })
      .addCase(fetchUserSubscription.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取用户订阅失败'
      })
      // createSubscription
      .addCase(createSubscription.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(createSubscription.fulfilled, (state, action: PayloadAction<Subscription | undefined>) => {
        state.isLoading = false
        state.userSubscription = action.payload || null
      })
      .addCase(createSubscription.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '创建订阅失败'
      })
      // cancelSubscription
      .addCase(cancelSubscription.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(cancelSubscription.fulfilled, (state, action) => {
        state.isLoading = false
        const payload = action.payload
        if (payload && state.userSubscription?.id === payload) {
          state.userSubscription.status = SubscriptionStatus.Cancelled
        }
      })
      .addCase(cancelSubscription.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '取消订阅失败'
      })
      // updateSubscription
      .addCase(updateSubscription.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(updateSubscription.fulfilled, (state, action: PayloadAction<Subscription | undefined>) => {
        state.isLoading = false
        state.userSubscription = action.payload || null
      })
      .addCase(updateSubscription.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '更新订阅失败'
      })
      // fetchOrderStats
      .addCase(fetchOrderStats.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchOrderStats.fulfilled, (state, action: PayloadAction<any>) => {
        state.isLoading = false
        state.orderStats = action.payload
      })
      .addCase(fetchOrderStats.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload as string || '获取订单统计失败'
      })
  },
})

export const {
  setCurrentOrder,
  setOrders,
  setError,
  clearError,
  setPagination,
  setSubscriptionPlans,
  setUserSubscription,
  setPaymentStatus,
  clearOrderState,
} = orderSlice.actions

export default orderSlice.reducer